# Calendar Trend Analysis

Raw daily weight is noisy, and missing dates matter. FitAdapt therefore builds a continuous daily
timeline and uses trailing calendar windows: a seven-day mean includes the current date plus six
prior dates, never future observations or merely the last seven submitted records.

Missing values remain missing. A rolling mean requires at least four measurements by default.
Window weight change compares the current trailing mean with the mean exactly one configured window
earlier, making the windows non-overlapping. These are descriptive features, not personalized
predictions. Synthetic validation does not prove real-world accuracy.
