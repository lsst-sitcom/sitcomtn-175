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

import pandas as pd

from lsst.summit.utils import ConsDbClient
from lsst.sitcom.tn175 import utils


def table_for_filter_focus_offset_study(cdb_client: ConsDbClient, day_obs: int) -> pd.DataFrame:
    """
    Query ConsDB to get a table required for the filter focus offset study.
    
    This table contains:
    - the sequence number,
    - day of observation,
    - physical rotator angle,
    - telescope elevation,
    - airmass,
    - observation start and end times,
    - focus position,
    - observation reason,
    - physical filter,
    - band,
    - PSF sigma median,
    - AOS FWHM,
    - CCD PSF sigma,
    - CCD Z4,
    - detector id.

    Parameters
    ----------
    cdb_client : ConsDbClient
        An instance of the ConsDbClient to use for querying.

    day_obs : int
        The day of observation to query for.

    Returns
    -------
    pd.DataFrame
        A DataFrame containing the query results.
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

    return _df
