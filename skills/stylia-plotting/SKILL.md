---
name: stylia-plotting
description: >
  How to create Python plots using the stylia package — Ersilia's matplotlib wrapper for publication-ready figures.
  ALWAYS use this skill when the user says anything like "make a plot", "plot this", "plot the results", "visualize",
  "prepare a plotting function", "show me a chart", "can you plot", "add a figure", or any similar phrasing during
  a coding session. This includes scatter plots, line plots, bar charts, heatmaps, histograms, ROC curves, and any
  other chart type. Also trigger on requests to visualize data, compare values, show distributions, or create any
  kind of figure — even if the user does not mention stylia or matplotlib explicitly. Never generate matplotlib
  figures without stylia — always use stylia.create_figure() instead of plt.figure() or plt.subplots().
---

# Stylia Plotting

All Python figures at Ersilia are created with the **stylia** package, which wraps matplotlib to enforce a consistent, publication-ready style.

## Hard rules

- **Never** call `plt.figure()`, `plt.subplots()`, or any raw matplotlib figure constructor. Always use `fig, axs = stylia.create_figure()`.
- **Always** retrieve each subplot with `ax = axs.next()` — one call per subplot, in order.
- **Never** call `plt.savefig()` or `plt.show()`. Always use `stylia.save_figure()`.
- **Never** set axis labels, titles, or panel letters with `ax.set_xlabel()`, `ax.set_ylabel()`, `ax.set_title()`, or similar. Always use `stylia.label(ax, ...)` — it handles font sizes, colors, and panel letter formatting consistently.
- **Always pass `xlabel` and `ylabel` to `stylia.label()`**, even when no label is needed — pass `xlabel=""` and `ylabel=""`. Omitting them causes stylia to insert a placeholder text.
- When writing helper functions for a specific plot type, **always accept `ax` as an argument** rather than creating a figure inside the function. The caller owns the figure; the function only draws into the axis it receives.
- **Set width and height only for single square panels** — omit both for all other plot types:
  - Single panel, square data space (ROC curve, scatter, confusion matrix, heatmap): `width=0.5, height=0.5`
  - Single panel, wide data (bar chart, line plot, histogram, time series): default (omit both)
  - Multi-panel figures: default (omit both)
- **Do not set marker sizes, line widths, or font sizes** unless the user explicitly asks. Stylia's defaults are already calibrated — leave them alone.

```python
# Good
def plot_scatter(ax, x, y, color):
    ax.scatter(x, y, color=color)

fig, axs = stylia.create_figure(1, 1)
ax = axs.next()
plot_scatter(ax, x, y, color)
stylia.save_figure("out.png")

# Bad — never create figures inside helper functions
def plot_scatter(x, y):
    fig, ax = plt.subplots()   # wrong
    ...
```

## Setup

```python
import stylia

stylia.set_format("slide")    # or "print"
stylia.set_style("ersilia")   # or "article"
```

Call `set_format()` and `set_style()` once at the top of your script. They update matplotlib's rcParams globally.

### Choosing format and style

Infer from context — do not ask the user unless there is genuinely no signal. Default to `slide` + `ersilia`.

| Context clues | format | style |
|---|---|---|
| "paper", "publication", "manuscript", "journal", "Nature" | `"print"` | `"article"` |
| "presentation", "slides", "talk", "deck" | `"slide"` | `"ersilia"` |
| "Ersilia brand", "website", "report" | `"slide"` | `"ersilia"` |
| No context | `"slide"` | `"ersilia"` |

Always state the chosen format and style in a brief comment so the user can easily override:

```python
# Format: slide | Style: ersilia — change with stylia.set_format() / stylia.set_style()
stylia.set_format("slide")
stylia.set_style("ersilia")
```

## Creating Figures

```python
fig, axs = stylia.create_figure(nrows, ncols, width=1.0, height=None)
```

- `nrows`, `ncols`: grid dimensions
- `width`: fraction of format width (default 1.0 = full width)
- `height`: fraction of format width (defaults to 0.5 for print, 0.3 for slide)
- `width_ratios`, `height_ratios`: optional list for unequal subplot sizing

Choose width and height based on plot type:

| Case | width | height |
|---|---|---|
| Single panel, square data (ROC, scatter, heatmap, confusion matrix) | `0.5` | `0.5` |
| Single panel, wide data (bar chart, line, histogram, time series) | default | default |
| Multi-panel | default | default |

```python
# Single square panel (e.g. ROC curve)
fig, axs = stylia.create_figure(1, 1, width=0.5, height=0.5)
ax = axs.next()

# Multi-panel
fig, axs = stylia.create_figure(2, 2)
ax = axs.next()   # first subplot
ax = axs.next()   # second subplot
stylia.save_figure("figure.png")
```

## Labeling Axes

```python
stylia.label(ax, xlabel="Time / s", ylabel="Signal", title="Overview", abc="A")
```

**Always pass `xlabel` and `ylabel` explicitly**, even when no label is needed — use an empty string. Omitting them entirely causes stylia to insert a placeholder. You may omit `title` and `abc` freely.

```python
# Good — no axis labels needed, but still passed explicitly
stylia.label(ax, xlabel="", ylabel="")

# Bad — stylia will add a placeholder label
stylia.label(ax)
```

## Running Scripts

Stylia must be run in a conda environment where it is installed — never assume the base environment. Before executing any script, find a non-base environment with stylia:

```bash
STYLIA_ENV=$(for env in $(conda env list | grep -v '#' | grep -v '^base' | awk '{print $1}'); do
  conda run -n $env python -c "import stylia" 2>/dev/null && echo $env && break
done)
```

Then run the script with:

```bash
conda run -n $STYLIA_ENV python plot.py
```

If no non-base environment has stylia, warn the user rather than falling back to base.

## Saving Figures

```python
stylia.save_figure("output.png")  # 600 DPI, tight layout
```

Save to PNG by default. Use PDF only when vector output is explicitly needed. If saving as PDF, `pdf.fonttype: 42` is set automatically on import, ensuring fonts are properly embedded.

## Auto-applied settings

These are handled automatically by stylia — no code needed:

- **Font**: Arial is registered and set as the default sans-serif font on import.
- **Grid, spines, tick colors, patch borders**: all styled correctly when you call `set_format()` / `set_style()`.
- **Color cycle**: `axes.prop_cycle` is set to the active style's palette. For simple plots where you make multiple `ax.plot()` or `ax.bar()` calls without explicitly assigning colors, matplotlib will automatically cycle through the Ersilia or Article palette — no need to manually pick colors for straightforward cases.
- **Legend**: `ax.legend()` is already styled (white semi-transparent frame, upper-right position). Just call it — no extra arguments needed unless you want to override the location.

## Colors

Infer the right color strategy from the plot type — don't default to named colors when a colormap would communicate the data better.

### When to use named colors

Use named colors for a small number of categorically distinct groups (up to the palette size: 8 for ersilia, 10 for article).

```python
nc = stylia.NamedColors()   # resolves to ErsiliaColors or ArticleColors per active style

# ErsiliaColors (ersilia style): plum, purple, mint, blue, yellow, pink, orange, gray
# ArticleColors (article style): crimson, turquoise, cobalt, periwinkle, orchid, fuchsia, tangerine, amber, lime, silver

ax.scatter(x, y, color=nc.plum)
```

### When to use a CategoricalPalette

Use `CategoricalPalette` when you have more groups than named colors, or when you need colors in a list (e.g. a bar chart with many bars):

```python
pal = stylia.CategoricalPalette("ersilia")  # or "npg", "okabe", "tol", "pastel"
colors = pal.get(n)                          # n perceptually distinct colors
```

If there are more categories than the palette has colors, use a `CyclicColormap` instead — it interpolates gracefully and wraps back to the start:

```python
cm = stylia.CyclicColormap("ersilia")
cm.fit(labels)   # labels can be integer indices
colors = cm.transform(labels)
ax.bar(x, heights, color=colors)
```

### When to use a colormap

Use a continuous colormap when color encodes a value, not just a category:

| Data type | Colormap class | Example preset |
|---|---|---|
| Density, magnitude, "less to more" | `FadingColormap` | `"plum"`, `"crimson"`, `"cobalt"` |
| Ordered / sequential range | `SpectralColormap` | `"ersilia"`, `"npg"` |
| Diverging (around a midpoint) | `DivergingColormap` | `"plum_mint"`, `"crimson_cobalt"` |
| Cyclic / phase / angle | `CyclicColormap` | `"ersilia"`, `"npg"` |

```python
cm = stylia.FadingColormap("plum")
cm.fit(values)
colors = cm.transform(values)
ax.scatter(x, y, c=colors)
```

### Mean + repetitions (lighten pattern)

When plotting individual repetitions alongside their mean (e.g. multiple train/test splits with a mean curve), use the full color for the mean and a lightened version for each repetition. This naturally draws the eye to the summary while keeping the individual traces visible.

```python
nc = stylia.NamedColors()

# Individual splits — lightened
for fold_fpr, fold_tpr in zip(all_fpr, all_tpr):
    ax.plot(fold_fpr, fold_tpr, color=nc.get("plum", lighten=0.5))

# Mean — full color
ax.plot(mean_fpr, mean_tpr, color=nc.plum)
stylia.label(ax, xlabel="FPR", ylabel="TPR", title="ROC curve")
```

Use the same principle for any plot that shows repetitions + summary: area plots, line charts with replicates, violin + individual points, etc.

## Size Constants

Stylia's defaults are already calibrated for each format — do not override them unless the user explicitly asks. If the user does ask, these constants are available:

```python
stylia.FONTSIZE_SMALL   # tick labels, annotations
stylia.FONTSIZE         # axis labels, legend
stylia.FONTSIZE_BIG     # panel titles

stylia.MARKERSIZE_SMALL # dense scatter
stylia.MARKERSIZE       # standard scatter
stylia.MARKERSIZE_BIG   # highlighted points

stylia.LINEWIDTH        # standard lines, spines
stylia.LINEWIDTH_THICK  # emphasis lines
```

## Complete Example

```python
import numpy as np
import stylia

# Format: slide | Style: ersilia — change with stylia.set_format() / stylia.set_style()
stylia.set_format("slide")
stylia.set_style("ersilia")

x = np.linspace(0, 10, 100)


def plot_lines(ax, x, groups, colors):
    for grp, color in zip(groups, colors):
        ax.plot(x, grp, color=color)
    stylia.label(ax, xlabel="x", ylabel="sin(x)", title="Lines", abc="A")


def plot_scatter(ax, x, y, values):
    cm = stylia.FadingColormap("plum")
    cm.fit(values)
    ax.scatter(x, y, c=cm.transform(values))
    stylia.label(ax, xlabel="x", ylabel="y", title="Scatter", abc="B")


groups = [np.sin(x + i) for i in range(3)]
pal = stylia.CategoricalPalette("ersilia")
colors = pal.get(3)

fig, axs = stylia.create_figure(1, 2)
plot_lines(axs.next(), x, groups, colors)
plot_scatter(axs.next(), x[:50], np.random.rand(50), np.random.rand(50))

stylia.save_figure("figure.png")
```

## What NOT to do

- `plt.figure(...)` — use `fig, axs = stylia.create_figure()` instead
- `plt.subplots(...)` — use `fig, axs = stylia.create_figure()` instead
- `plt.savefig(...)` — use `stylia.save_figure()` instead
- `plt.show()` — use `stylia.save_figure()` instead
- Creating figures inside helper functions — accept `ax` as an argument instead
- Hardcoded hex colors — use `stylia.NamedColors()` or a palette/colormap
- Setting `width` or `height` in `create_figure()` unless the plot requires a square data space (ROC curve, scatter, heatmap, confusion matrix) — in that case use `width=0.5, height=0.5`
- Setting `s=`, `linewidth=`, `fontsize=` or any size/width parameter unless the user asks — stylia's defaults are correct
- Calling `stylia.label(ax)` without `xlabel` and `ylabel` — always pass them explicitly, using `""` if no label is needed
