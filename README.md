[![Website](https://img.shields.io/badge/sitcomtn--175-lsst.io-brightgreen.svg)](https://sitcomtn-175.lsst.io)
[![CI](https://github.com/lsst-sitcom/sitcomtn-175/actions/workflows/ci.yaml/badge.svg)](https://github.com/lsst-sitcom/sitcomtn-175/actions/workflows/ci.yaml)

# Filter Change defocus variation study

## SITCOMTN-175

We are seeing variation in the filter change look-up-table that we do not understand yet. 
The focus offset that we need to apply is varying during the night and between night, and sometimes it is fixed. We need to look into the variation of that require focus offset as a function of other telescope parameter to understand the cause.

**Links:**

- Publication URL: https://sitcomtn-175.lsst.io
- Alternative editions: https://sitcomtn-175.lsst.io/v
- GitHub repository: https://github.com/lsst-sitcom/sitcomtn-175
- Build system: https://github.com/lsst-sitcom/sitcomtn-175/actions/


## Build this technical note

You can clone this repository and build the technote locally if your system has Python 3.11 or later:

```sh
git clone https://github.com/lsst-sitcom/sitcomtn-175
cd sitcomtn-175
make init
make html
```

Repeat the `make html` command to rebuild the technote after making changes.
If you need to delete any intermediate files for a clean build, run `make clean`.

The built technote is located at `_build/html/index.html`.

## Publishing changes to the web

This technote is published to https://sitcomtn-175.lsst.io whenever you push changes to the `main` branch on GitHub.
When you push changes to a another branch, a preview of the technote is published to https://sitcomtn-175.lsst.io/v.

## Editing this technical note

The main content of this technote is in `index.md` (a Markdown file parsed as [CommonMark/MyST](https://myst-parser.readthedocs.io/en/latest/index.html)).
Metadata and configuration is in the `technote.toml` file.
For guidance on creating content and information about specifying metadata and configuration, see the Documenteer documentation: https://documenteer.lsst.io/technotes.

## Installing as a Python Package

The notebooks in the `./notebook` folder use the code in the `./python` folder as a package. You will need to install this package using EUPS. Here are the steps:

```
# Declare the package
eups declare lsst_sitcom_tn175 v1 -r $PATH_TO_THIS_REPO/sitcomtn-175

# Install it
setup lsst_sitcom_tn175

# Test it
python -c "import lsst.sitcom.tn175; print(lsst.sitcom.tn175.__version__)"
```

The last command line should print the package version. It is Ok if it prints `?`, since versioning might not be fully implemented yet.

If you are running the notebooks in Nublado, you will have to update the `$HOME/notebooks/.user_setups` file with the same lines above. 
