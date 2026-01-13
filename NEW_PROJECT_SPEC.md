# EI ASSET Performance Dashboard - CSV Edition

## Project Overview

This project is a streamlined version of the EI ASSET Performance Analysis Dashboard that works directly with pre-extracted CSV data instead of parsing PDF reports. The primary focus is on **median-based analysis** to handle outliers effectively, while also providing average metrics for reference.

### Key Differences from Original Project
- **No PDF parsing** - Data is read directly from CSVs
- **Median-first analysis** - All primary metrics use median; averages shown as secondary
- **Simplified pipeline** - CSV → Analysis → Dashboard

---

## Project Structure

```
EI-Analysis-CSV/
├── dashboard.py                 # Streamlit interactive dashboard
├── load_data.py                 # CSV loading and data transformation
├── requirements.txt             # Python dependencies
├── data/
│   ├── student_performance.csv  # Student scores (name, class, subject, score, total)
│   └── skills_by_question.csv   # Skills tested per question (class, subject, question, skill)
└── output/
    └── school_data.json         # Processed data for dashboard (auto-generated)
```

---

## Input CSV Specifications

### 1. `data/student_performance.csv`

Contains individual student performance data.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `class_section` | string | Class and section identifier | `3-A`, `4-A`, `8-A` |
| `subject` | string | Subject name | `English`, `Maths`, `Science` |
| `student_name` | string | Full student name (uppercase) | `RAHUL SHARMA` |
| `score` | integer | Raw score achieved | `42` |
| `total_questions` | integer | Total questions in the test | `50` |

**Example:**
```csv
class_section,subject,student_name,score,total_questions
3-A,English,AANYA SHARMA,42,50
3-A,English,ARJUN PATEL,38,50
3-A,English,DIYA GUPTA,45,50
3-A,Maths,AANYA SHARMA,28,35
3-A,Maths,ARJUN PATEL,31,35
4-A,English,KAVYA REDDY,52,60
...
```

### 2. `data/skills_by_question.csv`

Maps questions to the skills they test, with class-level performance.

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `class_section` | string | Class and section identifier | `3-A` |
| `subject` | string | Subject name | `English` |
| `skill_name` | string | Name of the skill/competency | `Analyses ideas and details` |
| `questions` | string | Comma-separated question numbers | `1,5,12,18` |
| `section_performance` | float | Class average % for this skill | `72.5` |
| `school_performance` | float | School average % for this skill | `68.3` |

**Example:**
```csv
class_section,subject,skill_name,questions,section_performance,school_performance
3-A,English,Analyses ideas and details,"1,5,12,18",72.5,68.3
3-A,English,Deduces meaning of unfamiliar words,"3,8,14",65.0,62.1
3-A,English,Identifies facts and details,"2,6,9,15,20",78.2,75.0
3-A,Maths,Performs arithmetic operations,"1,4,7,10",80.0,76.5
3-A,Maths,Applies concepts of geometry,"2,5,8",68.5,65.2
...
```

---

## Requirements

### `requirements.txt`

```
streamlit>=1.28.0
plotly>=5.18.0
pandas>=2.0.0
numpy>=1.24.0
```

---

## Module Specifications

### 1. `load_data.py` - Data Loading & Transformation

This module handles CSV loading and transforms data into the format required by the dashboard.

```python
"""
EI ASSET Data Loader - CSV Edition

Loads student performance and skills data from CSVs and transforms
into dashboard-ready format with median-first analysis.
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import dataclass, asdict


@dataclass
class StudentResult:
    """Individual student performance."""
    name: str
    score: int
    total_questions: int
    percentage: float


@dataclass
class SkillPerformance:
    """Skill-wise class performance."""
    skill_name: str
    questions: List[int]
    section_performance: float
    school_performance: float


@dataclass
class ClassReport:
    """Complete report for a class-subject combination."""
    class_section: str
    subject: str
    total_students: int
    total_questions: int
    class_average: float      # Mean percentage
    class_median: float       # Median percentage (PRIMARY METRIC)
    students: List[StudentResult]
    skills: List[SkillPerformance]


def load_student_performance(csv_path: str = "data/student_performance.csv") -> pd.DataFrame:
    """
    Load student performance data from CSV.

    Returns:
        DataFrame with columns: class_section, subject, student_name, score, total_questions
    """
    df = pd.read_csv(csv_path)

    # Validate required columns
    required_cols = ['class_section', 'subject', 'student_name', 'score', 'total_questions']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Calculate percentage for each student
    df['percentage'] = (df['score'] / df['total_questions'] * 100).round(1)

    return df


def load_skills_data(csv_path: str = "data/skills_by_question.csv") -> pd.DataFrame:
    """
    Load skills-by-question mapping from CSV.

    Returns:
        DataFrame with columns: class_section, subject, skill_name, questions,
                               section_performance, school_performance
    """
    df = pd.read_csv(csv_path)

    # Validate required columns
    required_cols = ['class_section', 'subject', 'skill_name', 'questions',
                     'section_performance', 'school_performance']
    missing = set(required_cols) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Parse questions string to list of integers
    df['questions_list'] = df['questions'].apply(
        lambda x: [int(q.strip()) for q in str(x).split(',') if q.strip()]
    )

    return df


def calculate_class_statistics(student_df: pd.DataFrame,
                                class_section: str,
                                subject: str) -> Dict[str, Any]:
    """
    Calculate median and average statistics for a class-subject combination.

    IMPORTANT: Median is the PRIMARY metric; average is secondary.

    Returns:
        Dictionary with statistics including median, mean, min, max, quartiles
    """
    mask = (student_df['class_section'] == class_section) & \
           (student_df['subject'] == subject)
    class_data = student_df[mask]['percentage']

    if len(class_data) == 0:
        return None

    return {
        'median': float(class_data.median()),           # PRIMARY METRIC
        'average': float(class_data.mean().round(1)),   # Secondary metric
        'min': float(class_data.min()),
        'max': float(class_data.max()),
        'q1': float(class_data.quantile(0.25)),         # First quartile
        'q3': float(class_data.quantile(0.75)),         # Third quartile
        'std': float(class_data.std().round(1)),        # Standard deviation
        'count': int(len(class_data)),
        'below_median_count': int((class_data < class_data.median()).sum()),
        'below_60_count': int((class_data < 60).sum())  # At-risk threshold
    }


def build_class_report(student_df: pd.DataFrame,
                       skills_df: pd.DataFrame,
                       class_section: str,
                       subject: str) -> ClassReport:
    """
    Build a complete class report with median-first statistics.

    Args:
        student_df: Student performance DataFrame
        skills_df: Skills mapping DataFrame
        class_section: Class identifier (e.g., "3-A")
        subject: Subject name (e.g., "English")

    Returns:
        ClassReport object with all data
    """
    # Filter for this class-subject
    student_mask = (student_df['class_section'] == class_section) & \
                   (student_df['subject'] == subject)
    class_students = student_df[student_mask]

    skills_mask = (skills_df['class_section'] == class_section) & \
                  (skills_df['subject'] == subject)
    class_skills = skills_df[skills_mask]

    if len(class_students) == 0:
        return None

    # Build student results
    students = [
        StudentResult(
            name=row['student_name'],
            score=int(row['score']),
            total_questions=int(row['total_questions']),
            percentage=float(row['percentage'])
        )
        for _, row in class_students.iterrows()
    ]

    # Build skills list
    skills = [
        SkillPerformance(
            skill_name=row['skill_name'],
            questions=row['questions_list'],
            section_performance=float(row['section_performance']),
            school_performance=float(row['school_performance'])
        )
        for _, row in class_skills.iterrows()
    ]

    # Calculate statistics
    stats = calculate_class_statistics(student_df, class_section, subject)
    total_questions = int(class_students['total_questions'].iloc[0])

    return ClassReport(
        class_section=class_section,
        subject=subject,
        total_students=len(students),
        total_questions=total_questions,
        class_average=stats['average'],
        class_median=stats['median'],
        students=students,
        skills=skills
    )


def build_school_data(student_csv: str = "data/student_performance.csv",
                      skills_csv: str = "data/skills_by_question.csv") -> Dict[str, Any]:
    """
    Build complete school data structure for dashboard.

    This is the main entry point for data loading.

    Returns:
        Dictionary with school_info, classes, subjects, reports, and grade_medians
    """
    # Load CSVs
    student_df = load_student_performance(student_csv)
    skills_df = load_skills_data(skills_csv)

    # Get unique classes and subjects
    classes = sorted(student_df['class_section'].unique().tolist(),
                     key=lambda x: (int(x.split('-')[0]), x.split('-')[1]))
    subjects = sorted(student_df['subject'].unique().tolist())

    # Build reports for each class-subject combination
    reports = []
    for class_section in classes:
        for subject in subjects:
            report = build_class_report(student_df, skills_df, class_section, subject)
            if report:
                reports.append(asdict(report))

    # Calculate grade-level medians (across all subjects per grade)
    grade_medians = {}
    for class_section in classes:
        class_data = student_df[student_df['class_section'] == class_section]['percentage']
        grade_medians[class_section] = {
            'overall_median': float(class_data.median()),
            'overall_average': float(class_data.mean().round(1)),
            'by_subject': {}
        }
        for subject in subjects:
            mask = (student_df['class_section'] == class_section) & \
                   (student_df['subject'] == subject)
            subj_data = student_df[mask]['percentage']
            if len(subj_data) > 0:
                grade_medians[class_section]['by_subject'][subject] = {
                    'median': float(subj_data.median()),
                    'average': float(subj_data.mean().round(1))
                }

    # Calculate school-wide medians
    school_median = float(student_df['percentage'].median())
    school_average = float(student_df['percentage'].mean().round(1))

    return {
        'school_info': {
            'school_name': 'PEP School V2',
            'school_code': '5103484',
            'assessment_date': 'January 2026',
            'assessment_name': 'EI ASSET'
        },
        'classes': classes,
        'subjects': subjects,
        'reports': reports,
        'grade_medians': grade_medians,
        'school_statistics': {
            'median': school_median,      # PRIMARY METRIC
            'average': school_average,    # Secondary metric
            'total_students': len(student_df['student_name'].unique()),
            'total_assessments': len(student_df)
        }
    }


def save_school_data(data: Dict[str, Any],
                     output_path: str = "output/school_data.json") -> None:
    """Save processed school data to JSON for dashboard consumption."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"School data saved to {output_path}")


def load_school_data(json_path: str = "output/school_data.json") -> Dict[str, Any]:
    """Load processed school data from JSON."""
    with open(json_path, 'r') as f:
        return json.load(f)


# CLI entry point
if __name__ == "__main__":
    print("Loading data from CSVs...")
    data = build_school_data()
    save_school_data(data)

    print(f"\nData Summary:")
    print(f"  Classes: {data['classes']}")
    print(f"  Subjects: {data['subjects']}")
    print(f"  Total Reports: {len(data['reports'])}")
    print(f"  School Median: {data['school_statistics']['median']}%")
    print(f"  School Average: {data['school_statistics']['average']}%")
```

---

### 2. `dashboard.py` - Streamlit Dashboard

The dashboard focuses on **median as the primary metric** throughout all visualizations and analyses.

```python
"""
EI ASSET Performance Dashboard - CSV Edition

Interactive Streamlit dashboard with MEDIAN-FIRST analysis.
All primary metrics use median; averages shown as secondary reference.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
from pathlib import Path

# Page configuration
st.set_page_config(
    page_title="EI ASSET Performance Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .median-highlight {
        color: #1f4e79;
        font-weight: bold;
        font-size: 1.2em;
    }
    .average-secondary {
        color: #6c757d;
        font-size: 0.9em;
    }
    .good-performance { color: #28a745; }
    .warning-performance { color: #ffc107; }
    .danger-performance { color: #dc3545; }
    .primary-metric {
        background-color: #e3f2fd;
        border-left: 4px solid #1976d2;
        padding: 10px;
        margin: 5px 0;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_data():
    """Load school data from JSON (with caching for performance)."""
    json_path = Path("output/school_data.json")
    if not json_path.exists():
        # Auto-generate if missing
        from load_data import build_school_data, save_school_data
        data = build_school_data()
        save_school_data(data)
        return data

    with open(json_path, 'r') as f:
        return json.load(f)


def get_performance_color(value: float, metric_type: str = "percentage") -> str:
    """Return color based on performance thresholds."""
    if value >= 75:
        return "#28a745"  # Green - Good
    elif value >= 65:
        return "#ffc107"  # Yellow - Needs attention
    else:
        return "#dc3545"  # Red - At risk


def get_student_data(data: dict, class_section: str, student_name: str) -> list:
    """Get all subject data for a specific student."""
    student_data = []
    for report in data['reports']:
        if report['class_section'] == class_section:
            for student in report['students']:
                if student['name'] == student_name:
                    student_data.append({
                        'subject': report['subject'],
                        'score': student['score'],
                        'percentage': student['percentage'],
                        'total_questions': student['total_questions'],
                        'class_median': report['class_median'],    # PRIMARY
                        'class_average': report['class_average'],  # Secondary
                        'skills': report['skills']
                    })
    return student_data


def get_class_students(data: dict, class_section: str) -> list:
    """Get unique student names for a class."""
    students = set()
    for report in data['reports']:
        if report['class_section'] == class_section:
            for student in report['students']:
                students.add(student['name'])
    return sorted(list(students))


def create_spider_chart(student_data: list, student_name: str) -> go.Figure:
    """
    Create radar chart comparing student vs class MEDIAN (primary) and average (secondary).
    """
    subjects = [d['subject'] for d in student_data]
    student_scores = [d['percentage'] for d in student_data]
    class_medians = [d['class_median'] for d in student_data]
    class_averages = [d['class_average'] for d in student_data]

    fig = go.Figure()

    # Student performance trace
    fig.add_trace(go.Scatterpolar(
        r=student_scores + [student_scores[0]],
        theta=subjects + [subjects[0]],
        fill='toself',
        name=student_name,
        line_color='#1976d2',
        fillcolor='rgba(25, 118, 210, 0.3)'
    ))

    # Class MEDIAN trace (PRIMARY - emphasized)
    fig.add_trace(go.Scatterpolar(
        r=class_medians + [class_medians[0]],
        theta=subjects + [subjects[0]],
        fill='toself',
        name='Class Median',
        line_color='#388e3c',
        line_width=3,
        fillcolor='rgba(56, 142, 60, 0.2)'
    ))

    # Class AVERAGE trace (secondary - dashed)
    fig.add_trace(go.Scatterpolar(
        r=class_averages + [class_averages[0]],
        theta=subjects + [subjects[0]],
        name='Class Average',
        line_color='#ff9800',
        line_dash='dash',
        line_width=2
    ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        title=f"Performance Comparison: {student_name}",
        height=450
    )

    return fig


def create_skill_chart(skills: list, title: str = "Skill-wise Performance") -> go.Figure:
    """Create horizontal bar chart for skill performance."""
    skill_names = [s['skill_name'] for s in skills]
    performances = [s['section_performance'] for s in skills]
    colors = [get_performance_color(p) for p in performances]

    fig = go.Figure(go.Bar(
        x=performances,
        y=skill_names,
        orientation='h',
        marker_color=colors,
        text=[f"{p:.1f}%" for p in performances],
        textposition='outside'
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Performance (%)",
        yaxis_title="",
        xaxis=dict(range=[0, 100]),
        height=max(300, len(skills) * 40),
        margin=dict(l=200)
    )

    return fig


def create_class_distribution_chart(report: dict) -> go.Figure:
    """
    Create box plot showing score distribution with MEDIAN highlighted.
    Includes individual student points for transparency.
    """
    percentages = [s['percentage'] for s in report['students']]
    names = [s['name'] for s in report['students']]

    fig = go.Figure()

    # Box plot showing distribution with median
    fig.add_trace(go.Box(
        y=percentages,
        name='Score Distribution',
        boxpoints='all',
        jitter=0.3,
        pointpos=-1.8,
        marker=dict(color='#1976d2', size=8),
        line=dict(color='#1976d2'),
        text=names,
        hovertemplate='%{text}: %{y:.1f}%<extra></extra>'
    ))

    # Add median line annotation
    median_val = np.median(percentages)
    avg_val = np.mean(percentages)

    fig.add_hline(
        y=median_val,
        line_dash="solid",
        line_color="#388e3c",
        line_width=3,
        annotation_text=f"Median: {median_val:.1f}%",
        annotation_position="right"
    )

    fig.add_hline(
        y=avg_val,
        line_dash="dash",
        line_color="#ff9800",
        line_width=2,
        annotation_text=f"Average: {avg_val:.1f}%",
        annotation_position="left"
    )

    fig.update_layout(
        title=f"{report['class_section']} - {report['subject']}: Score Distribution",
        yaxis_title="Percentage (%)",
        yaxis=dict(range=[0, 100]),
        height=400,
        showlegend=False
    )

    return fig


def create_student_bar_chart(report: dict) -> go.Figure:
    """
    Create bar chart of student performance with MEDIAN reference line.
    """
    students = sorted(report['students'], key=lambda x: x['percentage'], reverse=True)
    names = [s['name'] for s in students]
    percentages = [s['percentage'] for s in students]
    colors = [get_performance_color(p) for p in percentages]

    fig = go.Figure(go.Bar(
        x=names,
        y=percentages,
        marker_color=colors,
        text=[f"{p:.1f}%" for p in percentages],
        textposition='outside'
    ))

    # Add MEDIAN line (PRIMARY - solid, prominent)
    fig.add_hline(
        y=report['class_median'],
        line_dash="solid",
        line_color="#388e3c",
        line_width=3,
        annotation_text=f"Median: {report['class_median']:.1f}%",
        annotation_position="right"
    )

    # Add average line (secondary - dashed)
    fig.add_hline(
        y=report['class_average'],
        line_dash="dash",
        line_color="#ff9800",
        line_width=2,
        annotation_text=f"Avg: {report['class_average']:.1f}%",
        annotation_position="left"
    )

    fig.update_layout(
        title=f"Student Performance - {report['class_section']} {report['subject']}",
        xaxis_title="Student",
        yaxis_title="Percentage (%)",
        yaxis=dict(range=[0, 105]),
        xaxis_tickangle=-45,
        height=450
    )

    return fig


def create_school_heatmap(data: dict) -> tuple:
    """
    Create heatmap of class vs subject performance using MEDIANS.
    """
    classes = data['classes']
    subjects = data['subjects']

    # Build median matrix
    matrix = []
    for cls in classes:
        row = []
        for subj in subjects:
            for report in data['reports']:
                if report['class_section'] == cls and report['subject'] == subj:
                    row.append(report['class_median'])  # Using MEDIAN
                    break
            else:
                row.append(None)
        matrix.append(row)

    df = pd.DataFrame(matrix, index=classes, columns=subjects)

    fig = px.imshow(
        df,
        labels=dict(x="Subject", y="Class", color="Median %"),
        x=subjects,
        y=classes,
        color_continuous_scale=["#dc3545", "#ffc107", "#28a745"],
        zmin=50,
        zmax=90,
        text_auto='.1f',
        aspect='auto'
    )

    fig.update_layout(
        title="School Performance Heatmap (by Median %)",
        height=400
    )

    return fig, df


def identify_at_risk_students(data: dict, threshold: float = 60.0) -> pd.DataFrame:
    """
    Identify students scoring below threshold (comparing to MEDIAN).
    A student is at-risk if below threshold in 2+ subjects.
    """
    student_scores = {}

    for report in data['reports']:
        cls = report['class_section']
        subj = report['subject']
        median = report['class_median']

        for student in report['students']:
            key = (cls, student['name'])
            if key not in student_scores:
                student_scores[key] = {'class': cls, 'name': student['name'], 'subjects': {}}

            student_scores[key]['subjects'][subj] = {
                'percentage': student['percentage'],
                'below_threshold': student['percentage'] < threshold,
                'vs_median': student['percentage'] - median
            }

    # Find at-risk students (below threshold in 2+ subjects)
    at_risk = []
    for key, info in student_scores.items():
        below_count = sum(1 for s in info['subjects'].values() if s['below_threshold'])
        if below_count >= 2:
            subjects_below = [
                f"{subj} ({info['subjects'][subj]['percentage']:.1f}%)"
                for subj, data in info['subjects'].items()
                if data['below_threshold']
            ]
            at_risk.append({
                'Class': info['class'],
                'Student': info['name'],
                'Subjects Below 60%': ', '.join(subjects_below),
                'Count': below_count
            })

    return pd.DataFrame(at_risk).sort_values(['Count', 'Class'], ascending=[False, True])


def display_median_metric(label: str, median: float, average: float, delta: float = None):
    """
    Display a metric with MEDIAN as primary and average as secondary.
    """
    col1, col2 = st.columns([3, 1])
    with col1:
        if delta is not None:
            st.metric(label=label, value=f"{median:.1f}%", delta=f"{delta:+.1f}%")
        else:
            st.metric(label=label, value=f"{median:.1f}%")
    with col2:
        st.caption(f"Avg: {average:.1f}%")


# ==================== MAIN DASHBOARD ====================

def main():
    # Load data
    data = load_data()
    school_info = data['school_info']

    # Header
    st.title("📊 EI ASSET Performance Dashboard")
    st.markdown(f"**{school_info['school_name']}** | School Code: {school_info['school_code']} | {school_info['assessment_date']}")

    # Median-first notice
    st.info("📌 **Median-First Analysis**: All primary metrics use median to account for outliers. Averages are shown as secondary reference.")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    tab_selection = st.sidebar.radio(
        "Select View:",
        ["🏫 School Overview", "📚 Class Analysis", "👤 Student Profile"]
    )

    # ==================== TAB 1: SCHOOL OVERVIEW ====================
    if tab_selection == "🏫 School Overview":
        st.header("School Overview")

        # School-wide metrics
        stats = data['school_statistics']
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("School Median", f"{stats['median']:.1f}%")
            st.caption(f"Average: {stats['average']:.1f}%")
        with col2:
            st.metric("Total Students", stats['total_students'])
        with col3:
            st.metric("Total Assessments", stats['total_assessments'])
        with col4:
            # Calculate students at risk
            at_risk_df = identify_at_risk_students(data)
            st.metric("At-Risk Students", len(at_risk_df))

        st.divider()

        # Performance Heatmap
        st.subheader("Performance by Class and Subject (Median %)")
        heatmap_fig, heatmap_df = create_school_heatmap(data)
        st.plotly_chart(heatmap_fig, use_container_width=True)

        # Grade-level median summary
        st.subheader("Grade-Level Medians")
        grade_data = []
        for cls in data['classes']:
            grade_info = data['grade_medians'][cls]
            row = {
                'Class': cls,
                'Overall Median': f"{grade_info['overall_median']:.1f}%",
                'Overall Average': f"{grade_info['overall_average']:.1f}%"
            }
            for subj in data['subjects']:
                if subj in grade_info['by_subject']:
                    subj_stats = grade_info['by_subject'][subj]
                    row[f"{subj} Median"] = f"{subj_stats['median']:.1f}%"
            grade_data.append(row)

        st.dataframe(pd.DataFrame(grade_data), use_container_width=True, hide_index=True)

        # At-risk students
        st.subheader("⚠️ At-Risk Students (Below 60% in 2+ Subjects)")
        if len(at_risk_df) > 0:
            st.dataframe(at_risk_df, use_container_width=True, hide_index=True)
        else:
            st.success("No students currently at risk.")

        # Weak skills across school
        st.subheader("📉 Skills Needing Attention (< 65%)")
        weak_skills = []
        for report in data['reports']:
            for skill in report['skills']:
                if skill['section_performance'] < 65:
                    weak_skills.append({
                        'Class': report['class_section'],
                        'Subject': report['subject'],
                        'Skill': skill['skill_name'],
                        'Performance': f"{skill['section_performance']:.1f}%"
                    })

        if weak_skills:
            weak_df = pd.DataFrame(weak_skills).sort_values('Performance')
            st.dataframe(weak_df.head(15), use_container_width=True, hide_index=True)
        else:
            st.success("All skills performing above 65%.")

    # ==================== TAB 2: CLASS ANALYSIS ====================
    elif tab_selection == "📚 Class Analysis":
        st.header("Class Analysis")

        # Class and subject selection
        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Class", data['classes'])
        with col2:
            selected_subject = st.selectbox("Select Subject", data['subjects'])

        # Find the report
        report = None
        for r in data['reports']:
            if r['class_section'] == selected_class and r['subject'] == selected_subject:
                report = r
                break

        if report:
            # Class metrics with MEDIAN first
            st.subheader(f"{selected_class} - {selected_subject}")

            col1, col2, col3, col4, col5 = st.columns(5)

            percentages = [s['percentage'] for s in report['students']]

            with col1:
                st.metric("Class Median", f"{report['class_median']:.1f}%")
                st.caption("PRIMARY METRIC")
            with col2:
                st.metric("Class Average", f"{report['class_average']:.1f}%")
                st.caption("Secondary")
            with col3:
                st.metric("Highest", f"{max(percentages):.1f}%")
            with col4:
                st.metric("Lowest", f"{min(percentages):.1f}%")
            with col5:
                below_60 = sum(1 for p in percentages if p < 60)
                st.metric("Below 60%", below_60)

            st.divider()

            # Distribution chart (box plot with median)
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(create_class_distribution_chart(report), use_container_width=True)
            with col2:
                # Quartile information
                st.subheader("Distribution Statistics")
                q1 = np.percentile(percentages, 25)
                q3 = np.percentile(percentages, 75)
                iqr = q3 - q1

                st.markdown(f"""
                | Statistic | Value |
                |-----------|-------|
                | **Median (Q2)** | **{report['class_median']:.1f}%** |
                | Average | {report['class_average']:.1f}% |
                | Q1 (25th percentile) | {q1:.1f}% |
                | Q3 (75th percentile) | {q3:.1f}% |
                | IQR | {iqr:.1f}% |
                | Min | {min(percentages):.1f}% |
                | Max | {max(percentages):.1f}% |
                | Std Dev | {np.std(percentages):.1f}% |
                """)

            # Student performance bar chart
            st.subheader("Individual Student Performance")
            st.plotly_chart(create_student_bar_chart(report), use_container_width=True)

            # Skill-wise performance
            st.subheader("Skill-wise Performance")
            if report['skills']:
                st.plotly_chart(create_skill_chart(report['skills']), use_container_width=True)

                # Skills summary
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**💪 Strong Skills (≥75%)**")
                    strong = [s for s in report['skills'] if s['section_performance'] >= 75]
                    for s in strong:
                        st.markdown(f"- {s['skill_name']}: {s['section_performance']:.1f}%")
                    if not strong:
                        st.caption("None")
                with col2:
                    st.markdown("**⚠️ Skills Needing Attention (<65%)**")
                    weak = [s for s in report['skills'] if s['section_performance'] < 65]
                    for s in weak:
                        st.markdown(f"- {s['skill_name']}: {s['section_performance']:.1f}%")
                    if not weak:
                        st.caption("None")

            # Student ranking table
            st.subheader("Student Rankings")
            students_sorted = sorted(report['students'], key=lambda x: x['percentage'], reverse=True)
            ranking_data = []
            for i, s in enumerate(students_sorted, 1):
                vs_median = s['percentage'] - report['class_median']
                status = "Above Median" if vs_median >= 0 else "Below Median"
                ranking_data.append({
                    'Rank': i,
                    'Name': s['name'],
                    'Score': f"{s['score']}/{s['total_questions']}",
                    'Percentage': f"{s['percentage']:.1f}%",
                    'vs Median': f"{vs_median:+.1f}%",
                    'Status': status
                })

            st.dataframe(pd.DataFrame(ranking_data), use_container_width=True, hide_index=True)
        else:
            st.warning("No data available for this selection.")

    # ==================== TAB 3: STUDENT PROFILE ====================
    elif tab_selection == "👤 Student Profile":
        st.header("Student Profile")

        # Class and student selection
        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Class", data['classes'])
        with col2:
            students = get_class_students(data, selected_class)
            selected_student = st.selectbox("Select Student", students)

        if selected_student:
            student_data = get_student_data(data, selected_class, selected_student)

            if student_data:
                st.subheader(f"📋 {selected_student}")

                # Performance summary with median comparison
                st.markdown("### Performance Summary")
                cols = st.columns(len(student_data))

                for i, subj_data in enumerate(student_data):
                    with cols[i]:
                        vs_median = subj_data['percentage'] - subj_data['class_median']
                        vs_avg = subj_data['percentage'] - subj_data['class_average']

                        st.metric(
                            label=subj_data['subject'],
                            value=f"{subj_data['percentage']:.1f}%",
                            delta=f"{vs_median:+.1f}% vs Median"
                        )
                        st.caption(f"Score: {subj_data['score']}/{subj_data['total_questions']}")
                        st.caption(f"Class Median: {subj_data['class_median']:.1f}%")
                        st.caption(f"Class Avg: {subj_data['class_average']:.1f}%")

                st.divider()

                # Spider chart
                st.subheader("Multi-Subject Comparison")
                st.plotly_chart(create_spider_chart(student_data, selected_student), use_container_width=True)

                # Performance analysis
                st.subheader("Performance Analysis")
                col1, col2 = st.columns(2)

                # Find strongest and weakest subjects (vs median)
                best_subj = max(student_data, key=lambda x: x['percentage'] - x['class_median'])
                worst_subj = min(student_data, key=lambda x: x['percentage'] - x['class_median'])

                with col1:
                    st.markdown("**💪 Strongest Subject (vs Median)**")
                    delta = best_subj['percentage'] - best_subj['class_median']
                    st.success(f"{best_subj['subject']}: {best_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")

                with col2:
                    st.markdown("**📈 Needs Focus (vs Median)**")
                    delta = worst_subj['percentage'] - worst_subj['class_median']
                    if delta < 0:
                        st.warning(f"{worst_subj['subject']}: {worst_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")
                    else:
                        st.info(f"{worst_subj['subject']}: {worst_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")

                # Subject-wise details
                st.subheader("Subject Details")
                for subj_data in student_data:
                    with st.expander(f"📚 {subj_data['subject']} - {subj_data['percentage']:.1f}%"):
                        st.markdown(f"""
                        - **Score**: {subj_data['score']} / {subj_data['total_questions']}
                        - **Percentage**: {subj_data['percentage']:.1f}%
                        - **Class Median**: {subj_data['class_median']:.1f}%
                        - **Class Average**: {subj_data['class_average']:.1f}%
                        - **vs Median**: {subj_data['percentage'] - subj_data['class_median']:+.1f}%
                        - **vs Average**: {subj_data['percentage'] - subj_data['class_average']:+.1f}%
                        """)

                        if subj_data['skills']:
                            st.markdown("**Skill-wise Class Performance:**")
                            st.plotly_chart(
                                create_skill_chart(subj_data['skills'], ""),
                                use_container_width=True
                            )
            else:
                st.warning("No data available for this student.")


if __name__ == "__main__":
    main()
```

---

## Running the Project

### 1. Setup

```bash
# Create project directory
mkdir EI-Analysis-CSV
cd EI-Analysis-CSV

# Create data directory
mkdir -p data output

# Install dependencies
pip install -r requirements.txt
```

### 2. Prepare CSV Files

Place your CSV files in the `data/` directory:
- `data/student_performance.csv`
- `data/skills_by_question.csv`

### 3. Generate School Data

```bash
python load_data.py
```

This will:
- Read both CSV files
- Calculate median and average statistics
- Generate `output/school_data.json`

### 4. Launch Dashboard

```bash
streamlit run dashboard.py
```

---

## Key Features: Median-First Analysis

### Why Median Over Average?

Median is more robust to outliers:

| Scenario | Scores | Average | Median |
|----------|--------|---------|--------|
| Normal distribution | 70, 72, 74, 76, 78 | 74.0% | 74.0% |
| With outlier | 70, 72, 74, 76, 20 | 62.4% | 72.0% |
| With high outlier | 70, 72, 74, 76, 98 | 78.0% | 74.0% |

The median gives a better sense of "typical" student performance.

### Where Median is Used

1. **School Overview**
   - School-wide median displayed as primary metric
   - Grade-level medians in summary table
   - Heatmap uses median percentages

2. **Class Analysis**
   - Class median is the primary reference line
   - Box plots show median prominently
   - Student rankings compare vs median

3. **Student Profile**
   - Performance delta shown vs class median
   - Spider chart includes median reference
   - Strongest/weakest determined by median comparison

4. **At-Risk Identification**
   - Students below 60% threshold flagged
   - Comparison includes both median and absolute threshold

---

## Customization Options

### Adjusting Thresholds

In `dashboard.py`, modify these values:

```python
# Performance color thresholds
def get_performance_color(value: float) -> str:
    if value >= 75:      # Good
        return "#28a745"
    elif value >= 65:    # Warning
        return "#ffc107"
    else:                # Danger
        return "#dc3545"

# At-risk threshold
def identify_at_risk_students(data: dict, threshold: float = 60.0):
    # Students below this % in 2+ subjects are flagged
```

### Adding New Metrics

In `load_data.py`, extend `calculate_class_statistics()`:

```python
def calculate_class_statistics(student_df, class_section, subject):
    # ... existing code ...
    return {
        'median': float(class_data.median()),
        'average': float(class_data.mean()),
        # Add new metrics:
        'mode': float(class_data.mode().iloc[0]) if len(class_data.mode()) > 0 else None,
        'skewness': float(class_data.skew()),
        'percentile_10': float(class_data.quantile(0.10)),
        'percentile_90': float(class_data.quantile(0.90)),
    }
```

---

## Sample Data for Testing

### `data/student_performance.csv`

```csv
class_section,subject,student_name,score,total_questions
3-A,English,AANYA SHARMA,42,50
3-A,English,ARJUN PATEL,38,50
3-A,English,DIYA GUPTA,45,50
3-A,English,ISHAAN REDDY,28,50
3-A,English,KAVYA NAIR,41,50
3-A,Maths,AANYA SHARMA,28,35
3-A,Maths,ARJUN PATEL,31,35
3-A,Maths,DIYA GUPTA,25,35
3-A,Maths,ISHAAN REDDY,18,35
3-A,Maths,KAVYA NAIR,30,35
3-A,Science,AANYA SHARMA,35,40
3-A,Science,ARJUN PATEL,32,40
3-A,Science,DIYA GUPTA,38,40
3-A,Science,ISHAAN REDDY,22,40
3-A,Science,KAVYA NAIR,36,40
```

### `data/skills_by_question.csv`

```csv
class_section,subject,skill_name,questions,section_performance,school_performance
3-A,English,Analyses ideas and details,"1,5,12,18",72.5,68.3
3-A,English,Deduces meaning of unfamiliar words,"3,8,14",65.0,62.1
3-A,English,Identifies facts and details,"2,6,9,15,20",78.2,75.0
3-A,English,Grammar and usage,"4,7,11,16,19",70.5,68.0
3-A,Maths,Performs arithmetic operations,"1,4,7,10",80.0,76.5
3-A,Maths,Applies concepts of geometry,"2,5,8",68.5,65.2
3-A,Maths,Understands fractions,"3,6,9",62.0,58.5
3-A,Science,Classifies objects and organisms,"1,5,9",75.0,72.0
3-A,Science,Interprets data from experiments,"2,6,10",70.0,67.5
3-A,Science,Formulates hypotheses,"3,7",58.0,55.0
```

---

## Migration from Original Project

If you have the original EI-Analysis project with extracted data, you can convert it:

```python
# convert_to_csv.py
import json
import pandas as pd

# Load existing school_data.json
with open('data/school_data.json', 'r') as f:
    data = json.load(f)

# Convert to student_performance.csv
students = []
for report in data['reports']:
    for student in report['students']:
        students.append({
            'class_section': report['class_section'],
            'subject': report['subject'],
            'student_name': student['name'],
            'score': student['score'],
            'total_questions': student['total_questions']
        })

pd.DataFrame(students).to_csv('data/student_performance.csv', index=False)

# Convert to skills_by_question.csv
skills = []
for report in data['reports']:
    for skill in report['skills']:
        skills.append({
            'class_section': report['class_section'],
            'subject': report['subject'],
            'skill_name': skill['skill_name'],
            'questions': ','.join(map(str, skill['questions'])),
            'section_performance': skill['section_performance'],
            'school_performance': skill['school_performance']
        })

pd.DataFrame(skills).to_csv('data/skills_by_question.csv', index=False)
```

---

## Summary

This CSV-based EI ASSET Dashboard provides:

1. **Simplified Data Pipeline**: Direct CSV input, no PDF parsing required
2. **Median-First Analysis**: All primary metrics use median to handle outliers
3. **Same Dashboard Experience**: Three-tab interface with student, class, and school views
4. **Easy Data Updates**: Simply update the CSV files and re-run
5. **Transparent Statistics**: Box plots, quartiles, and distribution metrics

The focus on median ensures that a single student with an extremely high or low score doesn't skew the class-level metrics, giving educators a more accurate picture of typical student performance.
