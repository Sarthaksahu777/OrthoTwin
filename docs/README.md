# OrthoTwin Modules 1-7: Clinical Decision-Support Prototype

This module provides a Streamlit viewer for lumbar spine MRI studies from the
RSNA 2024 Lumbar Spine Degenerative Classification dataset. Study and series
selectors are populated by scanning the image folders, and friendly series
names are read from `train_series_descriptions.csv`. The selected study's
degeneration labels are displayed from `train.csv` in a color-coded dashboard.
Sagittal series also support manual L4-L5 rectangle annotation.
The selected study is compared with all other labeled studies to retrieve the
five closest cases using normalized Manhattan distance.
The presentation layer organizes imaging, clinical labels, similar cases, and
educational treatment knowledge into four dashboard tabs.

## Folder structure

Canonical dataset layout:

```text
OrthoTwin/
|-- app.py
|-- annotations.json
|-- requirements.txt
|-- train.csv
|-- train_series_descriptions.csv
`-- train_images/
    `-- <study_id>/
        `-- <series_id>/
            |-- 1.dcm
            |-- 2.dcm
            `-- ...
```

The application also detects the current local layout, where `<study_id>`
folders are placed directly beside `app.py`.

## Run

From the project directory:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

Use the sidebar to choose a study and a friendly series name. Changing either
selection automatically reloads the corresponding DICOM volume. The dataset
and CSV paths can also be changed when the files are stored elsewhere. The
dashboard remains below the MRI viewer and updates with the selected study.

Enable **Show L4-L5 Focus Region** in the sidebar while viewing a sagittal
series. Draw a rectangle on the annotation canvas and select **Save L4-L5
Coordinates**. Coordinates are stored per study in `annotations.json` and the
saved region is overlaid on the MRI viewer.

Treatment content is general educational knowledge mapped to dataset severity
labels. It is not a diagnosis or patient-specific recommendation. AI
diagnosis, classification models, predictions, segmentation, outcome
prediction, and digital twin simulation are intentionally excluded.
