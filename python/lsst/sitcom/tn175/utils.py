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
import numpy as np

from astropy.time import Time

from lsst.summit.utils import getAirmassSeeingCorrection, getBandpassSeeingCorrection

__all__ = [
    "coerce_astropy_times",
    "convert_psf_sigma_to_fwhm",
]

# Convenience constant used for PSF FWHM conversion
SIGMA_TO_FWHM = 2 * np.sqrt(2 * np.log(2))
PIXEL_SCALE_ARCSEC = 0.2  # arcsec / pixel (LSSTCam)
CORNER_DETECTORS = (191, 192, 195, 196, 199, 200, 203, 204)


def coerce_astropy_times(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any astropy Time columns to UTC pandas datetime."""
    for col in df.columns:
        sample = df[col].dropna().iloc[0] if df[col].notna().any() else None
        if isinstance(sample, Time):
            df[col] = pd.to_datetime(
                df[col].apply(lambda t: t.utc.to_value("datetime64") if pd.notna(t) else pd.NaT)
            )
    return df


def convert_psf_sigma_to_fwhm(psf_sigma: pd.Series, airmass: pd.Series, band_p: pd.Series) -> pd.Series:
    """
    Convert PSF sigma to FWHM.

    Parameters
    ----------
    psf_sigma : float
        The PSF sigma value.

    Returns
    -------
    float
        The corresponding FWHM value.
    """
    # Convert PSF sigma (pixels) -> FWHM (arcsec)
    # NOTE: psf_sigma is the median sigma from visit1_quicklook.
    psf_fwhm = psf_sigma * SIGMA_TO_FWHM * PIXEL_SCALE_ARCSEC

    # Apply bandpass and airmass corrections
    airmass_correction = airmass.apply(getAirmassSeeingCorrection)
    bandpass_correction = band_p.apply(getBandpassSeeingCorrection)

    fwhm_zenith_500nm = psf_fwhm * airmass_correction * bandpass_correction
    return fwhm_zenith_500nm


def group_rows_by_detector(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group the table by detector IDs, pivoting the relevant metrics into
    separate columns. In other words, for each exposure ID, create columns
    like 'ccd_psf_sigma_dXX' and 'z4_dXX' where XX is the detector ID. Since 
    Zernikes are only calculated for corner detectors, only those detectors
    will have a 'z4_dXX' column. The other detectors will only have 
    'ccd_psf_sigma_dXX'.

    Parameters
    ----------
    df : pd.DataFrame
        The input DataFrame containing a 'detector_id' column.

    Returns
    -------
    pd.DataFrame
        A DataFrame grouped by detector IDs.
    """
    # Make sure we don't modify the original DataFrame
    df = df.copy()

    # Recover exposure ID - FIXED VERSION
    df["exp_id"] = df["day_obs"].astype(str) + "_" + df["seq"].astype(str).str.zfill(6)
    df = df[["exp_id"] + [col for col in df.columns if col != "exp_id"]]

    # Create a column to identify which metric to use per detector
    def get_pivot_column(row):
        if row["detector"] in CORNER_DETECTORS:
            return f"z4_d{row['detector']:03d}"
        else:
            return f"ccd_fwhm_zenith_500nm_d{row['detector']:03d}"

    def get_pivot_value(row):
        if row["detector"] in CORNER_DETECTORS:
            return row["ccd_z4"]
        else:
            return row["ccd_fwhm_zenith_500nm"]

    df["pivot_col"] = df.apply(get_pivot_column, axis=1)
    df["pivot_val"] = df.apply(get_pivot_value, axis=1)

    # Get columns that should be kept (same for all detectors in an exp_id)
    base_cols = [
        col
        for col in df.columns
        if col not in ["exp_id", "detector", "pivot_col", "pivot_val", "ccd_fwhm_zenith_500nm", "ccd_z4"]
    ]

    # Pivot the data
    result = df.pivot_table(
        index="exp_id", values="pivot_val", columns="pivot_col", aggfunc="first"
    ).reset_index()

    # Merge back the base columns (take first occurrence for each exp_id)
    base_df = df[["exp_id"] + base_cols].drop_duplicates(subset="exp_id")
    result = result.merge(base_df, on="exp_id")

    # Reorder to put exp_id first
    result = result[["exp_id"] + [col for col in result.columns if col != "exp_id"]]

    return result


def merge_double_zernikes(
    cdb_table: pd.DataFrame,
    dz_table: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge double Zernike measurements into the per-visit cdb_table.

    Parameters
    ----------
    cdb_table : pd.DataFrame
        Per-visit observatory table with visit as index.
    dz_table : pd.DataFrame
        Double Zernike table with a 'visit' column.

    Returns
    -------
    pd.DataFrame
        Merged table with visit as index and double Zernike columns appended.
    """
    # Columns that exist in both tables — no need to bring them in again
    shared_cols = set(cdb_table.reset_index().columns) & set(dz_table.columns)
    dz_cols_to_merge = [c for c in dz_table.columns if c not in shared_cols - {"visit"}]

    merged = cdb_table.reset_index().merge(
        dz_table[dz_cols_to_merge],
        on="visit",
        how="left",  # keep all visits in cdb_table; NaN where no dz measurement exists
    ).set_index("visit")

    # Ensure datetime columns are in UTC pandas datetime format
    merged = coerce_astropy_times(merged)

    return merged