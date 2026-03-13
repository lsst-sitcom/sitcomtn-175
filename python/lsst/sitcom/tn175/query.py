# This file is part of sitcomtn-175.
#
# Developed for the LSST Data Management System.
# This product includes software developed by the LSST Project
# (https://www.lsst.org).
# See the COPYRIGHT file at the top-level directory of this distribution
# for details of code ownership.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import galsim
import itertools
import numpy as np
import pandas as pd

from tqdm.notebook import tqdm

from lsst.daf.butler import Butler
from lsst.obs.lsst import LsstCam
from lsst.ts.ofc import OFCData
from lsst.summit.utils import ConsDbClient

from lsst.sitcom.tn175 import utils


def table_for_filter_focus_offset_study(cdb_client: ConsDbClient, day_obs: int, corner_detectors: list) -> pd.DataFrame:
    """
    Query ConsDB to generate a table for the filter focus offset study,
    aggregating and transforming relevant exposure and detector data.

    This function performs the following operations:
    - Queries ConsDB for exposures matching the specified observation day and
      image types ('science' or 'acq'), joining relevant tables to collect:
        - Sequence number, day of observation, physical rotator angle,
          telescope elevation, airmass, observation start/end times,
          focus position, observation reason, physical filter, band,
          PSF sigma median, AOS FWHM, CCD PSF sigma, CCD Z4, CCD Z11,
          and detector ID.

    - Filters out rows with airmass equal to zero.

    - Parses observation start and end times into datetime objects.

    - Converts PSF sigma values to FWHM at zenith and 500nm for both
      visit-level and CCD-level measurements.

    - Removes the original PSF sigma columns after conversion.

    - Constructs a unique visit identifier and sets it as the DataFrame index.

    - For each detector in `corner_detectors`, creates columns for Zernike
      coefficients (z4 and z11) specific to that detector, containing values
      only for matching detector rows.

    - Aggregates the table by visit, keeping the first value for most columns,
      the mean for CCD Zernike coefficients (z4, z11),
      and the first value for each per-detector Zernike column.

    - The final table contains one row per visit (for visits with corner
      detectors), with columns:
        - visit, seq, day_obs, physical_rotator_angle, altitude, airmass,
          obs_start, obs_end, focus_z, observation_reason, band_p, band,
          aos_fwhm, fwhm_zenith_500nm_median, ccd_fwhm_zenith_500nm,
          ccd_z4_mean, ccd_z11_mean,
          and for each corner detector: ccd_z4_d{det}, ccd_z11_d{det}.

    Parameters
    ----------
    cdb_client : ConsDbClient
        An instance of the ConsDbClient to use for querying.

    day_obs : int
        The day of observation to query for.

    corner_detectors : list
        List of detector IDs considered as corners for which per-detector
        Zernike columns are created.

    Returns
    -------
    pd.DataFrame
        Aggregated DataFrame indexed by visit, containing visit-level and
        per-corner-detector Zernike coefficients
        and relevant exposure metadata.
    """
    query = f"""
    SELECT
        e.seq_num AS seq,
        e.day_obs,
        q.physical_rotator_angle,
        e.altitude,
        e.airmass,
        e.obs_start,
        e.obs_end,
        e.focus_z,
        e.observation_reason,
        e.physical_filter as band_p,
        e.band,
        q.psf_sigma_median,
        q.aos_fwhm,
        ccdvisit1_quicklook.psf_sigma as ccd_psf_sigma,
        ccdvisit1_quicklook.z4 as ccd_z4,
        ccdvisit1_quicklook.z11 as ccd_z11,
        ccdvisit1.detector as detector
    FROM
        cdb_lsstcam.ccdvisit1_quicklook AS ccdvisit1_quicklook,
        cdb_lsstcam.ccdvisit1 AS ccdvisit1,
        cdb_lsstcam.visit1 AS visit1,
        cdb_lsstcam.visit1_quicklook AS q,
        cdb_lsstcam.exposure AS e
    WHERE
        ccdvisit1.ccdvisit_id = ccdvisit1_quicklook.ccdvisit_id
        AND ccdvisit1.visit_id = visit1.visit_id
        AND ccdvisit1.visit_id = q.visit_id
        AND ccdvisit1.visit_id = e.exposure_id
        AND q.visit_id = e.exposure_id
        AND (e.img_type = 'science' or e.img_type = 'acq')
        AND e.day_obs = {int(day_obs)}
    """
    _df = cdb_client.query(query).to_pandas()

    # Drop any data with the following criteria
    _df = _df[_df['airmass'] != 0]
    _df = _df.reset_index(drop=True)  # Reset index after filtering

    # Robust datetime parsing for mixed ISO8601 strings
    _df["obs_start"] = pd.to_datetime(_df["obs_start"], format="ISO8601", errors="coerce")
    _df["obs_end"] = pd.to_datetime(_df["obs_end"], format="ISO8601", errors="coerce")

    # In theory, this convertion should be already done in ConsDB. However,
    #  this column has not bee populated to this date. So we need to update 
    #  our table manually.
    _df["fwhm_zenith_500nm_median"] = utils.convert_psf_sigma_to_fwhm(
        psf_sigma=_df["psf_sigma_median"],
        airmass=_df["airmass"],
        band_p=_df["band_p"],
    )
    
    _df["ccd_fwhm_zenith_500nm"] = utils.convert_psf_sigma_to_fwhm(
        psf_sigma=_df["ccd_psf_sigma"],
        airmass=_df["airmass"],
        band_p=_df["band_p"],
    )
    
    del _df["psf_sigma_median"]
    del _df["ccd_psf_sigma"]
    
    # Create visitId to be used as an index later
    _df['visit'] = _df['day_obs'] * 1e5 + _df['seq']
    _df['visit'] = _df['visit'].astype('int')
    
    # Change the table index for easier matching later
    _df = _df.set_index("visit")

    # Let's keep z4 and z11 for the corner detectors
    for det in corner_detectors:
        _df[f"ccd_z4_d{det}"] = _df["ccd_z4"].where(_df["detector"] == det)
        _df[f"ccd_z11_d{det}"] = _df["ccd_z11"].where(_df["detector"] == det)

    # Let's create a list of new zernike columns for corner detectors
    new_zernike_cols = [f"ccd_z{z}_d{det}" for z in [4, 11] for det in corner_detectors]
    
    # Now we simplify our table using aggregation
    agg_dict = {
        col: "first"
        for col in _df.columns
        if col not in ("visit", "detector", "ccd_fwhm_zenith_500nm")
    }

    # "first" works here because each per-detector column has exactly one non-NaN per visit
    agg_dict.update({col: "first" for col in new_zernike_cols})
    agg_dict.update({col: "mean" for col in ["ccd_z4", "ccd_z11"]})

    # Perform aggregation
    _df = (
        _df[_df["detector"].isin(set(corner_detectors))]
        .groupby("visit", sort=True)
        .agg(agg_dict)
        .rename(columns={"ccd_z4": "ccd_z4_mean", "ccd_z11": "ccd_z11_mean"})
        .reset_index()
        .set_index("visit")
    )

    return _df


def butler_for_double_zernike_calculation(repo: str, collection: str, dataset: str, day_obs: int, corner_detectors: list) -> pd.DataFrame:
    """
    """
    # Initialize Butler
    butler = Butler(repo, collections=[collection])

    # TODO: There might be a more direct way of doing what I am doing here
    # TODO: update the `where` argument to ensure I only get science exposures
    datasets_results = butler.query_datasets(
        dataset,  
        where=f"exposure.day_obs = {day_obs}", 
        limit=None, 
        with_dimension_records=True
    )

    # Convert this list of DataSets into a dataframe with relevant information
    _df = pd.DataFrame([dict(dsr.dataId.mapping) for dsr in datasets_results])

    # Let's get the exposure begin and end for each visit
    _df["exp_begin_tai"] = [res.dataId.timespan.begin for res in datasets_results]
    _df["exp_end_tai"] = [res.dataId.timespan.end for res in datasets_results]

    # There is no need to keep the instrument
    _df.drop(columns="instrument", inplace=True)

    # Let's work with the `visit` as an index
    _df.set_index('visit', inplace=True)

    # Some debugging
    print(f"Got a list with {_df.index.size} dataset results.")
    
    # Initialize columns upfront
    z_coefficients = [f'Z{i}' for i in range(4, 27)]
    for detector in corner_detectors:
        for z_coef in z_coefficients:
            _df[f"d{detector}_{z_coef}"] = None

    # Process with progress bar
    print("Adding Zernike coefficients to the dataframe...")
    print(f"Processing {len(_df)} visits and {len(corner_detectors)} corner detectors.")
    total = len(_df) * len(corner_detectors)
    for visit, detector in tqdm(itertools.product(_df.index, corner_detectors), total=total, desc="Processing"):
        _add_zernikes_to_df(visit, detector, _df, butler)
    print("Finished adding Zernike coefficients.")
    print(f"DataFrame shape after adding Zernike coefficients: {_df.shape}")
        
    # Placeholders for the double zernikes
    dz_1_4 = []
    dz_2_4 = []

    print("Computing double Zernike coefficients for each visit...")
    # Loop over the visits and update the dataframe
    for visit in tqdm(_df.index):
        double_zernikes = _compute_double_zernikes(visit, _df)
    
        # Record gradients in focus
        dz_1_4.append(double_zernikes[1, 4]) 
        dz_2_4.append(double_zernikes[2, 4])

    # Update the dataframe
    _df["dz_1_4"] = dz_1_4
    _df["dz_2_4"] = dz_2_4
    
    print("Finished computing double Zernike coefficients.")
    return _df


def _add_zernikes_to_df(visit, detector, df, butler):
    """Add Zernike coefficients to dataframe for given visit and detector."""
    try:
        zernikes = butler.get('zernikes', visit=visit, detector=detector).to_pandas()
        
        # Get raw Zernike columns and their values
        z_cols = [col for col in zernikes.columns if col.startswith('Z') and '_' not in col]
        z_raw = zernikes[z_cols].values[0]  # First row
        
        # Assign each coefficient to its own column
        for i, z_col in enumerate(z_cols):
            df.at[visit, f"d{detector}_{z_col}"] = z_raw[i]
        
    except Exception as e:
        tqdm.write(f"  Failed: visit {visit}, detector {detector}: {e}")
        

def _compute_double_zernikes(visit, df):
    """
    Compute double Zernike coefficients for a given visit.
    
    Parameters
    ----------
    visit : int
        Visit ID
    df : DataFrame
        Dataframe with individual detector Zernike coefficients
    
    Returns
    -------
    dzs : array
        Double Zernike coefficients, shape (4, 29)
    """
    det_order = [191, 195, 199, 203]
    
    # Setup for double Zernike conversion
    camera = LsstCam().getCamera()
    detector_names = [camera.get(det_id).getName() for det_id in det_order]
    
    ofc_data = OFCData('lsst')
    field_angles = np.array([ofc_data.sample_points[sensor] for sensor in detector_names])
    
    kmax = 3
    basis = galsim.zernike.zernikeBasis(kmax, field_angles[:, 0], field_angles[:, 1], R_outer=1.75)

    # Zernike coefficients we have (Z20, Z21 are missing)
    z_coeffs = [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 22, 23, 24, 25, 26]
    
    # Create padded array for Z0-Z28 (29 total)
    zk_instance_padded = np.zeros((4, 29))
    
    # Fill in the Zernike values at their proper indices
    for i, detector in enumerate(det_order):
        for z in z_coeffs:
            zk_instance_padded[i, z] = df.at[visit, f'd{detector}_Z{z}']

    # double zernike expressions, dimensions (4, 25), 
    #   here 4 corresponds to k=0,1,2,3 
    #   which are the field dependencies we are allowing it to fit
    dzs, *_ = np.linalg.lstsq(basis.T, zk_instance_padded, rcond=None) 

    # the term k = 0 is meaningless, so we zero it out
    dzs[0, :] = 0.0 

    # Need to zero out the piston tip and tilt of zernikes, we only care about zk 4 and above
    dzs[:, :4] = 0.0 
    
    return dzs