# LaTeX Formatting: CUP Data & Policy Template

## Document Class
```latex
\documentclass{CUP-JNL-DAP}%
```

Required files in the same directory: `CUP-JNL-DAP.cls`, `CUP_Logo.eps`, `DAP_Logo_RGB.eps`, `orcid_logo.eps`. These come from the D&P author template zip.

## Required Packages
```latex
\usepackage{graphicx}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{booktabs}
\usepackage{tabularx}
\usepackage[authoryear]{natbib}
\usepackage[T1]{fontenc}
\usepackage{times}
\usepackage{newtxmath}
\usepackage{textcomp}
\usepackage{xcolor}
\usepackage{hyperref}
```

Do NOT include `sourcesanspro` (not available on all systems).

## Article Metadata
```latex
\articletype{DATA PAPER}
\jname{Data \& Policy}
\jyear{2026}
```

## Frontmatter Structure
```latex
\begin{Frontmatter}

\title[Short title for headers]{Full title}

\author*[1]{First Author}\email{email@university.edu}
\author[1]{Second Author}

\authormark{First Author \etal}

\address*[1]{\orgdiv{Department}, \orgname{University}, \orgaddress{\city{City}, \state{State}, \country{Country}}}

\keywords{keyword1; keyword2; keyword3}

\abstract{Abstract text (max 250 words).}

\begin{policy}
Policy significance statement (max 120 words).
\end{policy}

\end{Frontmatter}
```

## Section Headings
Use numbered sections (not `\section*{}`):
```latex
\section{Introduction}
\subsection{Subsection}
\subsubsection{Sub-subsection}
\paragraph{Paragraph heading}
```

## Figures
Use the `\FIG{}{}` wrapper:
```latex
\begin{figure}[!htbp]
\FIG{\includegraphics[width=\textwidth]{figures/filename.png}}
{\caption{Caption text.}
\label{fig:label}}
\end{figure}
```

## Tables
Use `\TBL{}{}`, `\TCH{}` for column headers, `\botrule` instead of `\bottomrule`:
```latex
\begin{table}[ht]
\TBL{\caption{Caption.\label{tab:label}}}
{\begin{tabularx}{\textwidth}{@{}lllX@{}}\toprule
\TCH{Col 1} & \TCH{Col 2} & \TCH{Col 3} & \TCH{Col 4} \\\midrule
data & data & data & data \\
\botrule
\end{tabularx}}
\end{table}
```

For tables without `tabularx` (fixed columns), use regular `tabular` inside `\TBL{}{}`.

## Backmatter Structure
```latex
\begin{Backmatter}

\paragraph{Acknowledgments}
Text including AI disclosure if applicable.

\paragraph{Funding Statement}
Funding text.

\paragraph{Competing Interests}
The author(s) declare none.

\paragraph{Data Availability Statement}
Text with Zenodo DOI and GitHub URL.

\paragraph{Ethical Standards}
Text about ethical compliance.

\paragraph{Author Contributions}
A.A. did X. B.B. did Y.

\begin{thebibliography}{}
% References in alphabetical order
\end{thebibliography}

\end{Backmatter}
```

## Citations
- Parenthetical: `\citep{key}` produces (Author, Year)
- Author-prominent: `\citet{key}` produces Author (Year)
- Never use `\textsuperscript{\cite{}}` (that is Scientific Data style)

## AI Disclosure (required if applicable)
Add to Acknowledgments:
```
The initial drafts of this manuscript were prepared with the assistance
of Claude (Anthropic), a large language model. All content was reviewed,
verified, and revised by the author, who takes full responsibility for
the accuracy of the text, data, and citations.
```
