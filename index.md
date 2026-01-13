# Filter Change defocus variation study

```{abstract}
We are seeing variation in the filter change look-up-table that we do not understand yet. The focus offset that we need to apply is varying during the night and between night, and sometimes it is fixed. We need to look into the variation of that require focus offset as a function of other telescope parameter to understand the cause.
```

# Introduction

# Building a new table

- `exposure_id`: The exposure (or visit) ID is a key identifier used within the Observatory's data management system, known as the Butler.

- `filter_id`: filter identifier.

- `fwhm_mean`: average full-width at half-maximum accross the field of view.

- `fwhm_std`: standard-deviation of the full-width at half-maximum accross the field of view.

- `fwhm_gradient_angle`: assuming that there is a linear gradient in the fwhm, get angle considering 0 degrees as matching plus x in pixels.

- `fwhm_gradient_strength`: assuming that there is a linear gradient in the fwhm, get the gradient strength accross the field of view. 

- `elevation_slew`: elevation angle at the begining of a slew prior to the exposure. 

- `elevation_track`: elevation tracking angle  

