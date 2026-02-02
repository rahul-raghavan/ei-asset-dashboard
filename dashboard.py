"""
EI ASSET Performance Dashboard

Interactive Streamlit dashboard focused on:
- National percentile standings (how students compare nationally)
- Skill-level analysis (actionable insights for teachers)
- Group analysis (for Montessori-style grouping)

Features:
- Password-based authentication with role-based access
- Management: Full access to all classes
- Elementary Program: Access to Classes 3-5
- Middle School Program: Access to Classes 6-8
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
from pathlib import Path
from config import PASSWORDS, ROLE_COLORS

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
    .percentile-excellent { color: #28a745; font-weight: bold; }
    .percentile-good { color: #17a2b8; }
    .percentile-average { color: #6c757d; }
    .percentile-below { color: #dc3545; }
    .award-badge {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        margin: 2px;
    }
    .award-outstanding { background-color: #FFD700; color: #333; }
    .award-distinguished { background-color: #C0C0C0; color: #333; }
    .award-creditable { background-color: #CD7F32; color: #fff; }
    .award-participation { background-color: #9E9E9E; color: #fff; }
    .ats-badge {
        background-color: #28a745;
        color: white;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75em;
        font-weight: 600;
    }
    .skill-weak { background-color: #ffebee; border-left: 4px solid #dc3545; padding: 10px; margin: 5px 0; }
    .skill-strong { background-color: #e8f5e9; border-left: 4px solid #28a745; padding: 10px; margin: 5px 0; }
    .login-container {
        max-width: 400px;
        margin: 100px auto;
        padding: 40px;
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .role-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ==================== AUTHENTICATION ====================

def check_password():
    """
    Check if user has entered a valid password and return their role info.
    Returns None if not authenticated, or dict with role info if authenticated.
    """
    # Initialize session state
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.role_info = None

    # If already authenticated, return role info
    if st.session_state.authenticated:
        return st.session_state.role_info

    # Show login form
    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("EI ASSET Dashboard")
        st.markdown("#### Please enter your password to continue")

        password = st.text_input("Password", type="password", key="password_input")

        if st.button("Login", type="primary", use_container_width=True):
            if password in PASSWORDS:
                st.session_state.authenticated = True
                st.session_state.role_info = PASSWORDS[password]
                st.rerun()
            else:
                st.error("Invalid password. Please try again.")

        st.markdown("---")
        st.caption("Contact administration if you need access credentials.")

    return None


def filter_data_by_role(data: dict, allowed_classes: list) -> dict:
    """
    Filter school data to only include classes the user has access to.
    """
    filtered_data = data.copy()

    # Filter classes
    filtered_data['classes'] = [c for c in data['classes'] if c in allowed_classes]

    # Filter reports
    filtered_data['reports'] = [
        r for r in data['reports']
        if r['class_section'] in allowed_classes
    ]

    # Filter grade_medians
    filtered_data['grade_medians'] = {
        k: v for k, v in data['grade_medians'].items()
        if k in allowed_classes
    }

    # Recalculate school statistics for filtered data
    if filtered_data['reports']:
        all_percentages = []
        total_students = 0
        student_names_by_class = {}

        for report in filtered_data['reports']:
            cls = report['class_section']
            if cls not in student_names_by_class:
                student_names_by_class[cls] = set()

            for student in report['students']:
                all_percentages.append(student['percentage'])
                student_names_by_class[cls].add(student['name'])

        total_students = sum(len(names) for names in student_names_by_class.values())

        filtered_data['school_statistics'] = {
            'median': float(np.median(all_percentages)) if all_percentages else 0,
            'average': float(round(np.mean(all_percentages), 1)) if all_percentages else 0,
            'total_students': total_students,
            'total_assessments': len(all_percentages)
        }

    return filtered_data


# ==================== DATA LOADING ====================

@st.cache_data(ttl=300)  # Cache for 5 minutes, then refresh
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
        data = json.load(f)

    # Validate that skill_performance data exists (critical for group analysis)
    # If not present, regenerate the data
    sample_report = data['reports'][0] if data.get('reports') else None
    if sample_report and sample_report.get('students'):
        sample_student = sample_report['students'][0]
        if not sample_student.get('skill_performance'):
            # Data is stale, regenerate
            from load_data import build_school_data, save_school_data
            data = build_school_data()
            save_school_data(data)

    return data


# ==================== HELPER FUNCTIONS ====================

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
                        'class_median': report['class_median'],
                        'class_average': report['class_average'],
                        'skills': report['skills'],
                        'question_responses': student.get('question_responses', []),
                        'skill_performance': student.get('skill_performance', {}),
                        'national': student.get('national'),  # National percentile data
                        'class_rank': None,  # Will be calculated below
                        'class_size': report['total_students']
                    })

    # Calculate class rank for each subject
    for subj_data in student_data:
        # Find all students in this class-subject and sort by percentage
        for report in data['reports']:
            if report['class_section'] == class_section and report['subject'] == subj_data['subject']:
                sorted_students = sorted(report['students'], key=lambda x: x['percentage'], reverse=True)
                for i, s in enumerate(sorted_students, 1):
                    if s['name'] == student_name:
                        subj_data['class_rank'] = i
                        break
                break

    return student_data


def get_student_overall_awards(data: dict, class_section: str, student_name: str) -> dict:
    """Get overall awards data for a student."""
    key = f"{class_section}|{student_name}"
    return data.get('student_overall_awards', {}).get(key)


def get_class_students(data: dict, class_section: str) -> list:
    """Get unique student names for a class."""
    students = set()
    for report in data['reports']:
        if report['class_section'] == class_section:
            for student in report['students']:
                students.add(student['name'])
    return sorted(list(students))


def get_all_students(data: dict) -> list:
    """Get all students across all classes with their basic info."""
    students = {}
    for report in data['reports']:
        cls = report['class_section']
        for student in report['students']:
            key = (cls, student['name'])
            if key not in students:
                students[key] = {
                    'class': cls,
                    'name': student['name'],
                    'display': f"{student['name']} ({cls})"
                }
    return sorted(students.values(), key=lambda x: (x['class'], x['name']))


def get_percentile_color(percentile: int) -> str:
    """Return color class based on national percentile."""
    if percentile >= 85:
        return "#28a745"  # Green - Excellent
    elif percentile >= 50:
        return "#17a2b8"  # Blue - Good/Above average
    elif percentile >= 25:
        return "#ffc107"  # Yellow - Average
    else:
        return "#dc3545"  # Red - Below average


def get_percentile_description(percentile: int) -> str:
    """Return human-readable description of percentile."""
    if percentile >= 99:
        return "Outstanding (Top 1%)"
    elif percentile >= 94:
        return "Distinguished (Top 6%)"
    elif percentile >= 85:
        return "Excellent (Top 15%)"
    elif percentile >= 50:
        return "Above Average"
    elif percentile >= 25:
        return "Average"
    else:
        return "Needs Support"


def get_award_html(award_code: str) -> str:
    """Return HTML badge for award code."""
    award_map = {
        'o': ('Outstanding', 'award-outstanding'),
        'd': ('Distinguished', 'award-distinguished'),
        'c': ('Creditable', 'award-creditable'),
        'p': ('Participation', 'award-participation')
    }
    label, css_class = award_map.get(award_code.lower(), ('Unknown', 'award-participation'))
    return f'<span class="award-badge {css_class}">{label}</span>'


def calculate_class_percentile_summary(data: dict, class_section: str) -> dict:
    """Calculate median percentiles for a class by subject."""
    summary = {'subjects': {}, 'overall_median': None}

    for report in data['reports']:
        if report['class_section'] == class_section:
            subject = report['subject']
            percentiles = []
            for student in report['students']:
                if student.get('national') and student['national'].get('percentile'):
                    percentiles.append(student['national']['percentile'])

            if percentiles:
                summary['subjects'][subject] = {
                    'median_percentile': int(np.median(percentiles)),
                    'min_percentile': min(percentiles),
                    'max_percentile': max(percentiles),
                    'ats_count': sum(1 for s in report['students']
                                    if s.get('national') and s['national'].get('ats_qualified'))
                }

    # Calculate overall median across subjects
    all_percentiles = []
    for subj_data in summary['subjects'].values():
        all_percentiles.append(subj_data['median_percentile'])
    if all_percentiles:
        summary['overall_median'] = int(np.median(all_percentiles))

    return summary


# ==================== CHART FUNCTIONS ====================

def create_spider_chart(student_data: list, student_name: str) -> go.Figure:
    """Create radar chart comparing student vs class MEDIAN and average."""
    subjects = [d['subject'] for d in student_data]
    student_scores = [d['percentage'] for d in student_data]
    class_medians = [d['class_median'] for d in student_data]
    class_averages = [d['class_average'] for d in student_data]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=student_scores + [student_scores[0]],
        theta=subjects + [subjects[0]],
        fill='toself',
        name=truncate_label(student_name, 18),
        line_color='#1976d2',
        fillcolor='rgba(25, 118, 210, 0.3)',
        hovertemplate='%{theta}: %{r:.1f}%<extra>Student</extra>'
    ))

    fig.add_trace(go.Scatterpolar(
        r=class_medians + [class_medians[0]],
        theta=subjects + [subjects[0]],
        fill='toself',
        name='Class Median',
        line_color='#388e3c',
        line_width=3,
        fillcolor='rgba(56, 142, 60, 0.2)',
        hovertemplate='%{theta}: %{r:.1f}%<extra>Median</extra>'
    ))

    fig.add_trace(go.Scatterpolar(
        r=class_averages + [class_averages[0]],
        theta=subjects + [subjects[0]],
        name='Class Average',
        line_color='#ff9800',
        line_dash='dash',
        line_width=2,
        hovertemplate='%{theta}: %{r:.1f}%<extra>Average</extra>'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=12))
        ),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.12, xanchor='center', x=0.5),
        title=f"Performance Comparison: {truncate_label(student_name, 25)}",
        height=480,
        margin=dict(l=60, r=60, t=60, b=80)
    )

    return fig


def truncate_label(text: str, max_len: int = 40) -> str:
    """Truncate long labels with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def create_skill_chart(skills: list, title: str = "Skill-wise Performance") -> go.Figure:
    """Create horizontal bar chart for skill performance."""
    skill_names = [s['skill_name'] for s in skills]
    truncated_names = [truncate_label(name, 45) for name in skill_names]
    performances = [s['section_performance'] for s in skills]
    colors = [get_performance_color(p) for p in performances]

    fig = go.Figure(go.Bar(
        x=performances,
        y=truncated_names,
        orientation='h',
        marker_color=colors,
        text=[f"{p:.1f}%" for p in performances],
        textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='<b>%{customdata}</b><br>Performance: %{x:.1f}%<extra></extra>',
        customdata=skill_names  # Full names for hover
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Performance (%)",
        yaxis_title="",
        xaxis=dict(range=[0, 105]),
        height=max(300, len(skills) * 45),
        margin=dict(l=280, r=40, t=40, b=40),
        yaxis=dict(tickfont=dict(size=11))
    )

    return fig


def create_class_distribution_chart(report: dict) -> go.Figure:
    """Create box plot showing score distribution with MEDIAN highlighted."""
    percentages = [s['percentage'] for s in report['students']]
    names = [s['name'] for s in report['students']]

    fig = go.Figure()

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

    median_val = np.median(percentages)
    avg_val = np.mean(percentages)

    # Position annotations to avoid overlap - median on right, avg on left with offset
    fig.add_hline(
        y=median_val,
        line_dash="solid",
        line_color="#388e3c",
        line_width=3,
        annotation_text=f"Median: {median_val:.1f}%",
        annotation_position="right",
        annotation=dict(font=dict(size=11, color="#388e3c"), bgcolor="white", borderpad=2)
    )

    fig.add_hline(
        y=avg_val,
        line_dash="dash",
        line_color="#ff9800",
        line_width=2,
        annotation_text=f"Avg: {avg_val:.1f}%",
        annotation_position="left",
        annotation=dict(font=dict(size=11, color="#ff9800"), bgcolor="white", borderpad=2)
    )

    fig.update_layout(
        title=f"{report['class_section']} - {report['subject']}: Score Distribution",
        yaxis_title="Percentage (%)",
        yaxis=dict(range=[0, 110]),
        height=420,
        showlegend=False,
        margin=dict(l=60, r=80, t=50, b=40)
    )

    return fig


def create_student_bar_chart(report: dict) -> go.Figure:
    """Create bar chart of student performance with MEDIAN reference line."""
    students = sorted(report['students'], key=lambda x: x['percentage'], reverse=True)
    num_students = len(students)

    # For many students, use horizontal bars for better readability
    if num_students > 15:
        # Horizontal bar chart for many students
        names = [s['name'] for s in students]
        truncated_names = [truncate_label(name, 20) for name in names]
        percentages = [s['percentage'] for s in students]
        colors = [get_performance_color(p) for p in percentages]

        fig = go.Figure(go.Bar(
            y=truncated_names,
            x=percentages,
            orientation='h',
            marker_color=colors,
            text=[f"{p:.1f}%" for p in percentages],
            textposition='inside',
            textfont=dict(color='white', size=10),
            hovertemplate='<b>%{customdata}</b><br>Score: %{x:.1f}%<extra></extra>',
            customdata=names
        ))

        fig.add_vline(
            x=report['class_median'],
            line_dash="solid",
            line_color="#388e3c",
            line_width=3,
            annotation_text=f"Median: {report['class_median']:.1f}%",
            annotation_position="top",
            annotation=dict(font=dict(size=10, color="#388e3c"), bgcolor="white")
        )

        fig.add_vline(
            x=report['class_average'],
            line_dash="dash",
            line_color="#ff9800",
            line_width=2,
            annotation_text=f"Avg: {report['class_average']:.1f}%",
            annotation_position="bottom",
            annotation=dict(font=dict(size=10, color="#ff9800"), bgcolor="white")
        )

        fig.update_layout(
            title=f"Student Performance - {report['class_section']} {report['subject']}",
            xaxis_title="Percentage (%)",
            yaxis_title="",
            xaxis=dict(range=[0, 110]),
            height=max(400, num_students * 28),
            margin=dict(l=160, r=50, t=50, b=40),
            yaxis=dict(tickfont=dict(size=10))
        )
    else:
        # Vertical bar chart for fewer students
        names = [s['name'] for s in students]
        # Truncate names for x-axis
        truncated_names = [truncate_label(name, 15) for name in names]
        percentages = [s['percentage'] for s in students]
        colors = [get_performance_color(p) for p in percentages]

        fig = go.Figure(go.Bar(
            x=truncated_names,
            y=percentages,
            marker_color=colors,
            text=[f"{p:.0f}%" for p in percentages],
            textposition='outside',
            textfont=dict(size=9),
            hovertemplate='<b>%{customdata}</b><br>Score: %{y:.1f}%<extra></extra>',
            customdata=names
        ))

        fig.add_hline(
            y=report['class_median'],
            line_dash="solid",
            line_color="#388e3c",
            line_width=3,
            annotation_text=f"Median: {report['class_median']:.1f}%",
            annotation_position="right",
            annotation=dict(font=dict(size=10, color="#388e3c"), bgcolor="white", borderpad=2)
        )

        fig.add_hline(
            y=report['class_average'],
            line_dash="dash",
            line_color="#ff9800",
            line_width=2,
            annotation_text=f"Avg: {report['class_average']:.1f}%",
            annotation_position="left",
            annotation=dict(font=dict(size=10, color="#ff9800"), bgcolor="white", borderpad=2)
        )

        fig.update_layout(
            title=f"Student Performance - {report['class_section']} {report['subject']}",
            xaxis_title="Student",
            yaxis_title="Percentage (%)",
            yaxis=dict(range=[0, 115]),
            xaxis_tickangle=-45,
            height=480,
            margin=dict(l=60, r=80, t=50, b=100)
        )

    return fig


def create_school_heatmap(data: dict) -> tuple:
    """Create heatmap of class vs subject performance using MEDIANS."""
    classes = data['classes']
    subjects = data['subjects']

    matrix = []
    for cls in classes:
        row = []
        for subj in subjects:
            for report in data['reports']:
                if report['class_section'] == cls and report['subject'] == subj:
                    row.append(report['class_median'])
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

    fig.update_traces(
        textfont=dict(size=14, color='black'),
        hovertemplate='Class: %{y}<br>Subject: %{x}<br>Median: %{z:.1f}%<extra></extra>'
    )

    fig.update_layout(
        title="Performance Heatmap (by Median %)",
        height=max(300, len(classes) * 60),
        margin=dict(l=80, r=40, t=50, b=60),
        xaxis=dict(tickfont=dict(size=12)),
        yaxis=dict(tickfont=dict(size=12))
    )

    return fig, df


def create_student_skill_radar(skill_performance: dict, class_skills: list, student_name: str) -> go.Figure:
    """Create a radar chart showing student's skill-wise performance vs class average."""
    if not skill_performance:
        return None

    skill_names = list(skill_performance.keys())
    # Truncate skill names for radar chart labels
    truncated_skills = [truncate_label(name, 25) for name in skill_names]
    student_values = list(skill_performance.values())

    # Get class-level performance for comparison
    class_values = []
    for skill_name in skill_names:
        for skill in class_skills:
            if skill['skill_name'] == skill_name:
                class_values.append(skill['section_performance'])
                break
        else:
            class_values.append(0)

    fig = go.Figure()

    # Student performance
    fig.add_trace(go.Scatterpolar(
        r=student_values + [student_values[0]],
        theta=truncated_skills + [truncated_skills[0]],
        fill='toself',
        name=truncate_label(student_name, 20),
        line_color='#1976d2',
        fillcolor='rgba(25, 118, 210, 0.3)',
        hovertemplate='%{theta}<br>Student: %{r:.1f}%<extra></extra>'
    ))

    # Class average for comparison
    fig.add_trace(go.Scatterpolar(
        r=class_values + [class_values[0]],
        theta=truncated_skills + [truncated_skills[0]],
        fill='toself',
        name='Class Average',
        line_color='#ff9800',
        line_dash='dash',
        fillcolor='rgba(255, 152, 0, 0.1)',
        hovertemplate='%{theta}<br>Class Avg: %{r:.1f}%<extra></extra>'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=9))
        ),
        showlegend=True,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        title=f"Skill Performance: {truncate_label(student_name, 25)}",
        height=450,
        margin=dict(l=80, r=80, t=60, b=60)
    )

    return fig


def create_skill_treemap(skill_performance: dict, title: str = "Skill Performance") -> go.Figure:
    """Create a treemap showing skill areas sized by performance."""
    if not skill_performance:
        return None

    skills = list(skill_performance.keys())
    truncated_skills = [truncate_label(s, 30) for s in skills]
    values = list(skill_performance.values())
    colors = [get_performance_color(v) for v in values]

    # For treemap, we need positive values for sizing
    # Use a base size + performance for visual appeal
    sizes = [max(10, v) for v in values]

    fig = go.Figure(go.Treemap(
        labels=[f"{s}<br>{v:.0f}%" for s, v in zip(truncated_skills, values)],
        parents=[""] * len(skills),
        values=sizes,
        marker=dict(colors=colors),
        textinfo="label",
        textfont=dict(size=11),
        hovertemplate="<b>%{customdata}</b><br>Performance: %{value:.0f}%<extra></extra>",
        customdata=skills  # Full skill names for hover
    ))

    fig.update_layout(
        title=title,
        height=380,
        margin=dict(t=50, l=10, r=10, b=10)
    )

    return fig


def create_skill_bar_comparison(skill_performance: dict, class_skills: list) -> go.Figure:
    """Create horizontal bar chart comparing student skills to class average.

    Uses grouped bars so both student and class values are always visible.
    Student bars are colored by performance level (green/yellow/red).
    Class average shown as gray bars with clear labels.
    """
    if not skill_performance:
        return None

    skills = list(skill_performance.keys())
    student_values = list(skill_performance.values())

    # Get class-level performance
    class_values = []
    for skill_name in skills:
        for skill in class_skills:
            if skill['skill_name'] == skill_name:
                class_values.append(skill['section_performance'])
                break
        else:
            class_values.append(0)

    # Sort by student performance (weakest first)
    combined = list(zip(skills, student_values, class_values))
    combined.sort(key=lambda x: x[1])  # Sort by student performance
    skills, student_values, class_values = zip(*combined)

    # Truncate skill names for display
    truncated_skills = [truncate_label(s, 40) for s in skills]

    fig = go.Figure()

    # Determine bar colors based on comparison to class average
    student_colors = []
    for sv, cv in zip(student_values, class_values):
        if sv >= cv + 10:
            student_colors.append('#28a745')  # Green - significantly above class
        elif sv >= cv - 10:
            student_colors.append('#ffc107')  # Yellow - near class average
        else:
            student_colors.append('#dc3545')  # Red - below class average

    # Class average bars (gray, always visible)
    fig.add_trace(go.Bar(
        y=truncated_skills,
        x=class_values,
        name='Class Average',
        orientation='h',
        marker_color='#9e9e9e',
        marker_line=dict(color='#757575', width=1),
        text=[f"{v:.0f}%" for v in class_values],
        textposition='outside',
        textfont=dict(color='#555', size=10),
        hovertemplate='<b>%{customdata}</b><br>Class Avg: %{x:.1f}%<extra></extra>',
        customdata=skills,
        offsetgroup=0
    ))

    # Student bars (colored by comparison, with special handling for 0%)
    # For 0% values, show a small bar with "0%" label
    student_display_values = [max(v, 2) for v in student_values]  # Min width for visibility
    student_text = []
    for v in student_values:
        if v == 0:
            student_text.append("0%")
        else:
            student_text.append(f"{v:.0f}%")

    fig.add_trace(go.Bar(
        y=truncated_skills,
        x=student_display_values,
        name='Student',
        orientation='h',
        marker_color=student_colors,
        marker_line=dict(color='#333', width=1),
        text=student_text,
        textposition='outside',
        textfont=dict(color='#333', size=10, weight='bold'),
        hovertemplate='<b>%{customdata}</b><br>Student: %{meta:.1f}%<extra></extra>',
        customdata=skills,
        meta=student_values,  # Store actual values for hover
        offsetgroup=1
    ))

    # Add difference indicators (arrows or text showing +/- vs class)
    annotations = []
    for i, (skill, sv, cv) in enumerate(zip(truncated_skills, student_values, class_values)):
        diff = sv - cv
        if diff > 0:
            diff_text = f"+{diff:.0f}"
            diff_color = "#28a745"
        elif diff < 0:
            diff_text = f"{diff:.0f}"
            diff_color = "#dc3545"
        else:
            diff_text = "="
            diff_color = "#666"

        # Position the difference indicator at the right side
        annotations.append(dict(
            x=105,
            y=i,
            text=diff_text,
            showarrow=False,
            font=dict(size=10, color=diff_color, weight='bold'),
            xanchor='left'
        ))

    fig.update_layout(
        title=dict(
            text="Skill Comparison: Student vs Class Average",
            font=dict(size=14)
        ),
        xaxis_title="Performance (%)",
        xaxis=dict(range=[0, 115], dtick=20),
        yaxis_title="",
        barmode='group',
        bargap=0.15,
        bargroupgap=0.05,
        height=max(380, len(skills) * 55),
        margin=dict(l=280, r=60, t=80, b=60),
        yaxis=dict(tickfont=dict(size=10)),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5,
            font=dict(size=11),
            itemsizing='constant'
        ),
        annotations=annotations
    )

    # Add a subtitle explaining the colors
    fig.add_annotation(
        text="<b>Student colors:</b> Green = above class | Yellow = near class | Red = below class | <b>Right column:</b> difference from class",
        xref="paper", yref="paper",
        x=0.5, y=-0.08,
        showarrow=False,
        font=dict(size=9, color="#666"),
        xanchor='center'
    )

    return fig


def create_question_heatmap(question_responses: list, skills: list, total_questions: int) -> go.Figure:
    """Create a visual heatmap of question responses grouped by skill."""
    if not question_responses or not skills:
        return None

    # Build question-to-skill mapping
    q_to_skill = {}
    for skill in skills:
        for q in skill['questions']:
            if q <= total_questions:
                q_to_skill[q] = skill['skill_name']

    # Group questions by skill
    skill_order = [s['skill_name'] for s in skills]
    skill_questions = {s: [] for s in skill_order}

    for q_num in range(1, total_questions + 1):
        skill = q_to_skill.get(q_num, "Other")
        if skill in skill_questions:
            skill_questions[skill].append((q_num, question_responses[q_num - 1] if q_num <= len(question_responses) else 0))

    # Create figure with subplots for each skill
    fig = go.Figure()

    y_pos = 0
    annotations = []

    for skill_name in skill_order:
        questions = skill_questions.get(skill_name, [])
        if not questions:
            continue

        for i, (q_num, correct) in enumerate(questions):
            color = '#28a745' if correct else '#dc3545'
            fig.add_trace(go.Scatter(
                x=[i],
                y=[y_pos],
                mode='markers',
                marker=dict(
                    size=22,
                    color=color,
                    symbol='square',
                    line=dict(color='white', width=1)
                ),
                hovertemplate=f"Q{q_num}: {'Correct' if correct else 'Incorrect'}<extra>{skill_name}</extra>",
                showlegend=False
            ))

            # Add question number text
            annotations.append(dict(
                x=i, y=y_pos,
                text=str(q_num),
                showarrow=False,
                font=dict(color='white', size=8)
            ))

        # Add skill label - truncated
        truncated_skill = truncate_label(skill_name, 35)
        annotations.append(dict(
            x=-0.8, y=y_pos,
            text=truncated_skill,
            showarrow=False,
            xanchor='right',
            font=dict(size=9)
        ))

        y_pos += 1

    fig.update_layout(
        title="Question Responses by Skill",
        height=max(200, y_pos * 45 + 80),
        xaxis=dict(visible=False, range=[-1, max(len(q) for q in skill_questions.values() if q) + 0.5]),
        yaxis=dict(visible=False, range=[-0.5, y_pos - 0.5]),
        annotations=annotations,
        margin=dict(l=240, r=20, t=50, b=20),
        showlegend=False
    )

    return fig


def create_class_skill_heatmap(report: dict) -> go.Figure:
    """Create a heatmap showing how each student performs on each skill."""
    students = report.get('students', [])
    skills = report.get('skills', [])

    if not students or not skills:
        return None

    # Filter students with skill performance data
    students_with_data = [s for s in students if s.get('skill_performance')]
    if not students_with_data:
        return None

    skill_names = [sk['skill_name'] for sk in skills]

    # Create unique truncated labels
    truncated_skills = []
    seen = {}
    for name in skill_names:
        truncated = truncate_label(name, 30)
        if truncated in seen:
            seen[truncated] += 1
            truncated = f"{truncated[:-3]}({seen[truncated]})"
        else:
            seen[truncated] = 1
        truncated_skills.append(truncated)

    student_names = [s['name'] for s in students_with_data]
    truncated_students = [truncate_label(n, 18) for n in student_names]

    # Build matrix: students x skills
    matrix = []
    for student in students_with_data:
        row = []
        for skill_name in skill_names:
            perf = student.get('skill_performance', {}).get(skill_name, 0)
            row.append(perf)
        matrix.append(row)

    df = pd.DataFrame(matrix, index=truncated_students, columns=truncated_skills)

    # Sort students by overall performance
    df['_avg'] = df.mean(axis=1)
    df = df.sort_values('_avg', ascending=False)
    df = df.drop('_avg', axis=1)

    # Use go.Heatmap for better control
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=list(df.columns),
        y=list(df.index),
        colorscale=[[0, "#dc3545"], [0.5, "#ffc107"], [1, "#28a745"]],
        zmin=0,
        zmax=100,
        text=[[f"{v:.0f}" for v in row] for row in df.values],
        texttemplate="%{text}",
        textfont=dict(size=9),
        hovertemplate='Student: %{y}<br>Skill: %{x}<br>Performance: %{z:.1f}%<extra></extra>',
        colorbar=dict(title="Performance %")
    ))

    num_skills = len(truncated_skills)
    num_students = len(students_with_data)

    fig.update_layout(
        title="Student Performance by Skill",
        height=max(400, num_students * 35 + 200),
        margin=dict(l=140, r=60, t=50, b=180),
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=9),
            side='bottom'
        ),
        yaxis=dict(tickfont=dict(size=10))
    )

    return fig


def calculate_class_skill_gaps(report: dict) -> list:
    """Calculate which skills the class struggles with most."""
    students = report.get('students', [])
    skills = report.get('skills', [])

    if not students or not skills:
        return []

    skill_stats = []
    for skill in skills:
        skill_name = skill['skill_name']
        class_perf = skill['section_performance']

        # Get individual student performances for this skill
        student_perfs = []
        for student in students:
            sp = student.get('skill_performance', {})
            if skill_name in sp:
                student_perfs.append(sp[skill_name])

        if student_perfs:
            below_65 = sum(1 for p in student_perfs if p < 65)
            below_50 = sum(1 for p in student_perfs if p < 50)

            skill_stats.append({
                'skill_name': skill_name,
                'class_performance': class_perf,
                'students_below_65': below_65,
                'students_below_50': below_50,
                'pct_struggling': (below_65 / len(student_perfs)) * 100 if student_perfs else 0,
                'questions': skill['questions']
            })

    # Sort by most struggling (highest percentage below 65%)
    skill_stats.sort(key=lambda x: -x['pct_struggling'])
    return skill_stats


def get_all_students_for_subject(data: dict, subject: str) -> list:
    """Get all students across all classes for a specific subject."""
    students = []
    for report in data['reports']:
        if report['subject'] == subject:
            for student in report['students']:
                students.append({
                    'name': student['name'],
                    'class': report['class_section'],
                    'display': f"{student['name']} ({report['class_section']})",
                    'percentage': student['percentage'],
                    'skill_performance': student.get('skill_performance', {}),
                    'question_responses': student.get('question_responses', []),
                    'score': student['score'],
                    'total_questions': student['total_questions']
                })
    return students


def get_skills_by_class(data: dict, subject: str) -> dict:
    """
    Get skills organized by class for a given subject.

    Returns:
        Dict mapping class_section -> list of skill dicts
    """
    skills_by_class = {}
    for report in data['reports']:
        if report['subject'] == subject and report['skills']:
            skills_by_class[report['class_section']] = report['skills']
    return skills_by_class


def analyze_cross_grade_skills(group_students: list, skills_by_class: dict) -> dict:
    """
    Analyze skills across different grades in a student group.

    Returns:
        Dict with:
        - 'common_skills': Skills that appear in ALL grades represented in the group
        - 'grade_specific_skills': Dict mapping grade -> skills unique to that grade
        - 'all_skills_by_grade': Dict mapping grade -> all skills for that grade
        - 'grades_in_group': List of grades represented in the group
    """
    # Get unique grades in the group
    grades_in_group = sorted(set(s['class'] for s in group_students))

    if len(grades_in_group) <= 1:
        # Single grade - all skills are "common"
        grade = grades_in_group[0] if grades_in_group else None
        if grade and grade in skills_by_class:
            return {
                'common_skills': skills_by_class[grade],
                'grade_specific_skills': {},
                'all_skills_by_grade': {grade: skills_by_class[grade]},
                'grades_in_group': grades_in_group
            }
        return {
            'common_skills': [],
            'grade_specific_skills': {},
            'all_skills_by_grade': {},
            'grades_in_group': grades_in_group
        }

    # Get skill names by grade
    skills_names_by_grade = {}
    all_skills_by_grade = {}
    for grade in grades_in_group:
        if grade in skills_by_class:
            grade_skills = skills_by_class[grade]
            skills_names_by_grade[grade] = set(s['skill_name'] for s in grade_skills)
            all_skills_by_grade[grade] = grade_skills
        else:
            skills_names_by_grade[grade] = set()
            all_skills_by_grade[grade] = []

    # Find common skills (intersection of all grades)
    if skills_names_by_grade:
        common_skill_names = set.intersection(*skills_names_by_grade.values()) if skills_names_by_grade.values() else set()
    else:
        common_skill_names = set()

    # Build common skills list (use first grade's skill objects as reference)
    common_skills = []
    if common_skill_names and grades_in_group:
        first_grade = grades_in_group[0]
        if first_grade in all_skills_by_grade:
            for skill in all_skills_by_grade[first_grade]:
                if skill['skill_name'] in common_skill_names:
                    common_skills.append(skill)

    # Find grade-specific skills
    grade_specific_skills = {}
    for grade in grades_in_group:
        specific_names = skills_names_by_grade.get(grade, set()) - common_skill_names
        if specific_names:
            grade_specific_skills[grade] = [
                s for s in all_skills_by_grade.get(grade, [])
                if s['skill_name'] in specific_names
            ]

    return {
        'common_skills': common_skills,
        'grade_specific_skills': grade_specific_skills,
        'all_skills_by_grade': all_skills_by_grade,
        'grades_in_group': grades_in_group
    }


def analyze_group_skill_gaps_by_grade(students: list, skills: list, target_grades: list = None) -> pd.DataFrame:
    """
    Analyze skill gaps for a group of students, optionally filtering by specific grades.

    Args:
        students: List of student dicts
        skills: List of skill dicts
        target_grades: If provided, only analyze students from these grades

    Returns:
        DataFrame with skill gap analysis
    """
    if not students or not skills:
        return pd.DataFrame()

    # Filter students by grade if specified
    if target_grades:
        students = [s for s in students if s['class'] in target_grades]

    if not students:
        return pd.DataFrame()

    skill_data = []
    for skill in skills:
        skill_name = skill['skill_name']

        # Get each student's performance on this skill
        performances = []
        students_below_65 = []
        students_below_50 = []

        for student in students:
            sp = student.get('skill_performance', {})
            if skill_name in sp:
                perf = sp[skill_name]
                performances.append(perf)
                if perf < 65:
                    students_below_65.append(f"{student['name']} ({student['class']})")
                if perf < 50:
                    students_below_50.append(f"{student['name']} ({student['class']})")

        if performances:
            avg_perf = sum(performances) / len(performances)
            skill_data.append({
                'Skill': skill_name,
                'Group Avg': round(avg_perf, 1),
                'Students Below 65%': len(students_below_65),
                'Students Below 50%': len(students_below_50),
                '% Struggling': round(100 * len(students_below_65) / len(performances), 0),
                'Who Needs Help': ', '.join(students_below_65[:5]) + ('...' if len(students_below_65) > 5 else ''),
                'Questions': ', '.join(f"Q{q}" for q in skill.get('questions', []))
            })

    df = pd.DataFrame(skill_data)
    if not df.empty:
        df = df.sort_values('% Struggling', ascending=False)
    return df


def analyze_group_skill_gaps(students: list, skills: list) -> pd.DataFrame:
    """Analyze skill gaps for a group of students."""
    if not students or not skills:
        return pd.DataFrame()

    skill_data = []
    for skill in skills:
        skill_name = skill['skill_name']

        # Get each student's performance on this skill
        performances = []
        students_below_65 = []
        students_below_50 = []

        for student in students:
            sp = student.get('skill_performance', {})
            if skill_name in sp:
                perf = sp[skill_name]
                performances.append(perf)
                if perf < 65:
                    students_below_65.append(student['name'])
                if perf < 50:
                    students_below_50.append(student['name'])

        if performances:
            avg_perf = sum(performances) / len(performances)
            skill_data.append({
                'Skill': skill_name,
                'Group Avg': round(avg_perf, 1),
                'Students Below 65%': len(students_below_65),
                'Students Below 50%': len(students_below_50),
                '% Struggling': round(100 * len(students_below_65) / len(performances), 0),
                'Who Needs Help': ', '.join(students_below_65[:5]) + ('...' if len(students_below_65) > 5 else ''),
                'Questions': ', '.join(f"Q{q}" for q in skill['questions'])
            })

    df = pd.DataFrame(skill_data)
    if not df.empty:
        df = df.sort_values('% Struggling', ascending=False)
    return df


def create_group_skill_heatmap(students: list, skills: list, title: str = "Group Skill Performance Heatmap") -> go.Figure:
    """Create a heatmap showing skill performance for a group of students."""
    if not students or not skills:
        return None

    skill_names = [s['skill_name'] for s in skills]

    # Create unique truncated labels by adding index if duplicates exist
    truncated_skills = []
    seen = {}
    for i, name in enumerate(skill_names):
        truncated = truncate_label(name, 30)
        if truncated in seen:
            # Add suffix to make unique
            seen[truncated] += 1
            truncated = f"{truncated[:-3]}({seen[truncated]})"
        else:
            seen[truncated] = 1
        truncated_skills.append(truncated)

    student_labels = [f"{truncate_label(s['name'], 15)} ({s['class']})" for s in students]

    # Build matrix
    matrix = []
    for student in students:
        row = []
        sp = student.get('skill_performance', {})
        for skill_name in skill_names:
            row.append(sp.get(skill_name, 0))
        matrix.append(row)

    df = pd.DataFrame(matrix, index=student_labels, columns=truncated_skills)

    # Use go.Heatmap for more control over layout
    fig = go.Figure(data=go.Heatmap(
        z=df.values,
        x=truncated_skills,
        y=student_labels,
        colorscale=[[0, "#dc3545"], [0.5, "#ffc107"], [1, "#28a745"]],
        zmin=0,
        zmax=100,
        text=[[f"{v:.0f}" for v in row] for row in df.values],
        texttemplate="%{text}",
        textfont=dict(size=10),
        hovertemplate='Student: %{y}<br>Skill: %{x}<br>Performance: %{z:.1f}%<extra></extra>',
        colorbar=dict(title="Performance %")
    ))

    # Calculate dimensions
    num_skills = len(truncated_skills)
    num_students = len(student_labels)

    fig.update_layout(
        title=title,
        height=max(400, num_students * 40 + 200),
        width=max(600, num_skills * 80 + 200),
        margin=dict(l=160, r=60, t=60, b=180),
        xaxis=dict(
            tickangle=-45,
            tickfont=dict(size=10),
            side='bottom',
            tickmode='array',
            tickvals=list(range(len(truncated_skills))),
            ticktext=truncated_skills
        ),
        yaxis=dict(
            tickfont=dict(size=10),
            autorange='reversed'
        )
    )

    return fig


def load_saved_groups() -> dict:
    """Load saved student groups from file."""
    groups_file = Path("output/student_groups.json")
    if groups_file.exists():
        with open(groups_file, 'r') as f:
            return json.load(f)
    return {}


def save_groups(groups: dict) -> None:
    """Save student groups to file."""
    groups_file = Path("output/student_groups.json")
    with open(groups_file, 'w') as f:
        json.dump(groups, f, indent=2)


def identify_at_risk_students(data: dict, threshold: float = 60.0) -> pd.DataFrame:
    """Identify students scoring below threshold in 2+ subjects."""
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

    at_risk = []
    for key, info in student_scores.items():
        below_count = sum(1 for s in info['subjects'].values() if s['below_threshold'])
        if below_count >= 2:
            subjects_below = [
                f"{subj} ({info['subjects'][subj]['percentage']:.1f}%)"
                for subj, subj_data in info['subjects'].items()
                if subj_data['below_threshold']
            ]
            at_risk.append({
                'Class': info['class'],
                'Student': info['name'],
                'Subjects Below 60%': ', '.join(subjects_below),
                'Count': below_count
            })

    if not at_risk:
        return pd.DataFrame(columns=['Class', 'Student', 'Subjects Below 60%', 'Count'])

    return pd.DataFrame(at_risk).sort_values(['Count', 'Class'], ascending=[False, True])


# ==================== MAIN DASHBOARD ====================

def main():
    # Check authentication first
    role_info = check_password()

    if role_info is None:
        # Not authenticated, login form is shown by check_password()
        return

    # Load and filter data based on role
    full_data = load_data()
    data = filter_data_by_role(full_data, role_info['allowed_classes'])
    school_info = full_data['school_info']

    # Header with role indicator
    col_title, col_role = st.columns([3, 1])
    with col_title:
        st.title("EI ASSET Performance Dashboard")
        st.markdown(f"**{school_info['school_name']}** | School Code: {school_info['school_code']} | {school_info['assessment_date']}")

    with col_role:
        role_color = ROLE_COLORS.get(role_info['role'], '#666')
        st.markdown(
            f"<div style='text-align: right; padding-top: 20px;'>"
            f"<span class='role-badge' style='background-color: {role_color}; color: white;'>"
            f"{role_info['name']}</span><br>"
            f"<small style='color: #666;'>Classes: {', '.join(role_info['allowed_classes'])}</small>"
            f"</div>",
            unsafe_allow_html=True
        )

    # Median-first notice
    st.info("**Median-First Analysis**: All primary metrics use median to account for outliers. Averages are shown as secondary reference.")

    # Sidebar navigation
    st.sidebar.title("Navigation")
    tab_selection = st.sidebar.radio(
        "Select View:",
        ["School Overview", "Class Analysis", "Student Profile", "Group Analysis"]
    )

    # Show role info in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Logged in as:** {role_info['name']}")
    st.sidebar.caption(role_info['description'])

    # ==================== TAB 1: SCHOOL OVERVIEW ====================
    if tab_selection == "School Overview":
        st.header("School Overview")

        awards_summary = data.get('awards_summary')
        student_overall_awards = data.get('student_overall_awards', {})
        allowed_classes = role_info['allowed_classes']
        is_filtered = len(allowed_classes) < 6  # Not full access

        # Calculate filtered awards for the user's classes
        if is_filtered and student_overall_awards:
            filtered_awards = {'outstanding': 0, 'distinguished': 0, 'creditable': 0, 'participation': 0}
            filtered_ats = set()
            filtered_ats_by_subject = {}

            for key, award_data in student_overall_awards.items():
                cls = key.split('|')[0]
                if cls in allowed_classes:
                    award = award_data.get('overall_award', 'p').lower()
                    if award == 'o':
                        filtered_awards['outstanding'] += 1
                    elif award == 'd':
                        filtered_awards['distinguished'] += 1
                    elif award == 'c':
                        filtered_awards['creditable'] += 1
                    else:
                        filtered_awards['participation'] += 1

            # Count ATS by looking at student data in filtered reports
            for report in data['reports']:
                if report['class_section'] in allowed_classes:
                    subj = report['subject']
                    for student in report['students']:
                        if student.get('national') and student['national'].get('ats_qualified'):
                            student_key = f"{report['class_section']}|{student['name']}"
                            filtered_ats.add(student_key)
                            if subj not in filtered_ats_by_subject:
                                filtered_ats_by_subject[subj] = 0
                            filtered_ats_by_subject[subj] += 1

            filtered_total = sum(filtered_awards.values())
            filtered_ats_count = len(filtered_ats)

        # ===== Section 1: Overall Awards Distribution =====
        if awards_summary:
            st.subheader("Overall Awards Distribution")
            if is_filtered:
                st.caption(f"School-wide totals shown. **Your classes ({', '.join(allowed_classes)}):** {filtered_total} students")
            else:
                st.caption("Overall awards are based on combined performance across ALL subjects nationally.")

            col1, col2, col3, col4, col5 = st.columns(5)
            dist = awards_summary['award_distribution']

            with col1:
                if is_filtered:
                    st.metric("Outstanding", dist['outstanding'], delta=f"{filtered_awards['outstanding']} yours", delta_color="off")
                else:
                    st.metric("Outstanding", dist['outstanding'])
                st.caption("Top 1% nationally")
            with col2:
                if is_filtered:
                    st.metric("Distinguished", dist['distinguished'], delta=f"{filtered_awards['distinguished']} yours", delta_color="off")
                else:
                    st.metric("Distinguished", dist['distinguished'])
                st.caption("Top 2-6%")
            with col3:
                if is_filtered:
                    st.metric("Creditable", dist['creditable'], delta=f"{filtered_awards['creditable']} yours", delta_color="off")
                else:
                    st.metric("Creditable", dist['creditable'])
                st.caption("Top 7-17%")
            with col4:
                if is_filtered:
                    st.metric("Participation", dist['participation'], delta=f"{filtered_awards['participation']} yours", delta_color="off")
                else:
                    st.metric("Participation", dist['participation'])
                st.caption("Below top 17%")
            with col5:
                if is_filtered:
                    st.metric("Total Students", awards_summary['total_students_with_awards'], delta=f"{filtered_total} yours", delta_color="off")
                else:
                    st.metric("Total Students", awards_summary['total_students_with_awards'])

            # ATS Summary
            st.divider()
            st.subheader("Asset Talent Search (ATS) Qualifiers")
            if is_filtered:
                st.caption(f"Students in top 15% nationally. **Your classes:** {filtered_ats_count} unique qualifiers")
            else:
                st.caption("Students in top 15% nationally for each subject. A student can qualify in multiple subjects.")

            if awards_summary.get('ats_by_subject'):
                ats_cols = st.columns(len(awards_summary['ats_by_subject']) + 1)
                with ats_cols[0]:
                    if is_filtered:
                        st.metric("Total Unique", awards_summary['ats_qualified_count'], delta=f"{filtered_ats_count} yours", delta_color="off")
                    else:
                        st.metric("Total Unique", awards_summary['ats_qualified_count'])
                    st.caption("Students with ATS")
                for i, (subj, count) in enumerate(sorted(awards_summary['ats_by_subject'].items())):
                    with ats_cols[i + 1]:
                        if is_filtered:
                            yours = filtered_ats_by_subject.get(subj, 0)
                            st.metric(subj, count, delta=f"{yours} yours", delta_color="off")
                        else:
                            st.metric(subj, count)

        # ===== Section 2: Class-wise National Standing =====
        st.divider()
        st.subheader("Class-wise National Standing")
        st.caption("Median national percentile for each class-subject. 50th = national average. Higher is better.")

        # Build percentile heatmap data
        percentile_data = []
        for cls in data['classes']:
            row = {'Class': cls}
            class_summary = calculate_class_percentile_summary(data, cls)
            for subj in data['subjects']:
                if subj in class_summary['subjects']:
                    median_pct = class_summary['subjects'][subj]['median_percentile']
                    row[subj] = median_pct
                else:
                    row[subj] = None
            if class_summary['overall_median']:
                row['Overall'] = class_summary['overall_median']
            percentile_data.append(row)

        percentile_df = pd.DataFrame(percentile_data)

        # Create heatmap
        if not percentile_df.empty:
            subjects_for_heatmap = data['subjects'] + ['Overall']
            heatmap_values = percentile_df[subjects_for_heatmap].values

            fig = go.Figure(data=go.Heatmap(
                z=heatmap_values,
                x=subjects_for_heatmap,
                y=percentile_df['Class'].tolist(),
                colorscale=[[0, "#dc3545"], [0.5, "#ffc107"], [1, "#28a745"]],
                zmin=25,
                zmax=90,
                text=[[f"{v:.0f}" if pd.notna(v) else "" for v in row] for row in heatmap_values],
                texttemplate="%{text}",
                textfont=dict(size=14, color="black"),
                hovertemplate='Class: %{y}<br>Subject: %{x}<br>Median Percentile: %{z:.0f}th<extra></extra>',
                colorbar=dict(title="Percentile")
            ))

            fig.update_layout(
                title="Median National Percentile by Class",
                height=max(300, len(data['classes']) * 60),
                margin=dict(l=80, r=40, t=50, b=60),
                xaxis=dict(tickfont=dict(size=12)),
                yaxis=dict(tickfont=dict(size=12))
            )

            st.plotly_chart(fig, use_container_width=True)

        # Table with more details
        with st.expander("View detailed class breakdown"):
            detail_data = []
            for cls in data['classes']:
                class_summary = calculate_class_percentile_summary(data, cls)
                row = {'Class': cls}
                for subj in data['subjects']:
                    if subj in class_summary['subjects']:
                        s = class_summary['subjects'][subj]
                        row[f"{subj} Median"] = f"{s['median_percentile']}th"
                        row[f"{subj} ATS"] = s['ats_count']
                    else:
                        row[f"{subj} Median"] = "N/A"
                        row[f"{subj} ATS"] = 0
                detail_data.append(row)

            st.dataframe(pd.DataFrame(detail_data), use_container_width=True, hide_index=True)

        # ===== Section 3: Quick Student Lookup =====
        st.divider()
        st.subheader("Quick Student Lookup")
        st.caption("Select any student to see their national percentiles.")

        all_students = get_all_students(data)
        student_options = [s['display'] for s in all_students]
        selected_display = st.selectbox("Select Student", student_options, key="overview_student_lookup")

        if selected_display:
            # Find the student
            selected_student_info = next((s for s in all_students if s['display'] == selected_display), None)
            if selected_student_info:
                student_class = selected_student_info['class']
                student_name = selected_student_info['name']

                # Get overall awards
                overall_awards = get_student_overall_awards(data, student_class, student_name)
                student_subj_data = get_student_data(data, student_class, student_name)

                # Display student info
                col1, col2 = st.columns([1, 3])

                with col1:
                    if overall_awards:
                        st.markdown(get_award_html(overall_awards['overall_award']), unsafe_allow_html=True)
                        if overall_awards['total_percentile'] > 0:
                            st.metric("Overall Percentile", f"{overall_awards['total_percentile']:.0f}th")
                        else:
                            st.caption("Overall: Incomplete")

                with col2:
                    # Subject percentiles
                    subj_cols = st.columns(len(student_subj_data))
                    for i, subj_data in enumerate(student_subj_data):
                        with subj_cols[i]:
                            st.markdown(f"**{subj_data['subject']}**")
                            if subj_data.get('national'):
                                nat = subj_data['national']
                                pct_color = get_percentile_color(nat['percentile'])
                                st.markdown(f"<span style='color: {pct_color}; font-size: 1.5em; font-weight: bold;'>{nat['percentile']}th</span>",
                                           unsafe_allow_html=True)
                                st.caption(f"Scaled: {nat['scaled_score']}")
                                if nat['ats_qualified']:
                                    st.markdown('<span class="ats-badge">ATS Qualified</span>', unsafe_allow_html=True)
                            else:
                                st.caption("N/A")

        # ===== Section 4: Skills Needing Attention =====
        st.divider()
        st.subheader("Skills Needing Attention Across School")
        st.caption("Skills where class performance is below 65%.")

        weak_skills = []
        for report in data['reports']:
            for skill in report['skills']:
                if skill['section_performance'] < 65:
                    weak_skills.append({
                        'Class': report['class_section'],
                        'Subject': report['subject'],
                        'Skill': skill['skill_name'],
                        'Class Score': f"{skill['section_performance']:.0f}%"
                    })

        if weak_skills:
            weak_df = pd.DataFrame(weak_skills).sort_values('Class Score')
            st.dataframe(weak_df.head(15), use_container_width=True, hide_index=True)
        else:
            st.success("All skills performing above 65% across the school.")

    # ==================== TAB 2: CLASS VIEW ====================
    elif tab_selection == "Class Analysis":
        st.header("Class View")

        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Class", data['classes'])
        with col2:
            selected_subject = st.selectbox("Select Subject", data['subjects'])

        report = None
        for r in data['reports']:
            if r['class_section'] == selected_class and r['subject'] == selected_subject:
                report = r
                break

        if report:
            # ===== Section 1: National Standing Summary =====
            st.subheader(f"{selected_class} - {selected_subject}: National Standing")

            students_with_national = [s for s in report['students'] if s.get('national')]

            if students_with_national:
                percentiles = [s['national']['percentile'] for s in students_with_national]
                ats_qualifiers = [s['name'] for s in students_with_national if s['national'].get('ats_qualified')]

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    median_pct = int(np.median(percentiles))
                    st.metric("Class Median Percentile", f"{median_pct}th")
                    st.caption(get_percentile_description(median_pct))
                with col2:
                    st.metric("Highest", f"{max(percentiles)}th")
                with col3:
                    st.metric("Lowest", f"{min(percentiles)}th")
                with col4:
                    st.metric("ATS Qualified", len(ats_qualifiers))
                    st.caption("Top 15% nationally")

                if ats_qualifiers:
                    st.success(f"**ATS Qualified:** {', '.join(ats_qualifiers)}")

                st.divider()

                # ===== Section 2: All Students - National Percentiles =====
                st.subheader("Student National Percentiles")
                st.caption("Sorted by national percentile. Click column headers to re-sort.")

                # Build student table sorted by national percentile
                students_sorted = sorted(students_with_national,
                                        key=lambda x: x['national']['percentile'], reverse=True)

                student_table = []
                for s in students_sorted:
                    nat = s['national']
                    row = {
                        'Name': s['name'],
                        'National Percentile': nat['percentile'],
                        'Percentile Band': get_percentile_description(nat['percentile']),
                        'Scaled Score': nat['scaled_score'],
                        'Test Score': f"{s['score']}/{s['total_questions']}",
                        'ATS': "Yes" if nat['ats_qualified'] else ""
                    }
                    student_table.append(row)

                st.dataframe(pd.DataFrame(student_table), use_container_width=True, hide_index=True)

            else:
                st.info("National percentile data not available for this class/subject.")
                # Show basic score info instead
                st.subheader("Test Scores")
                score_table = []
                for s in sorted(report['students'], key=lambda x: x['percentage'], reverse=True):
                    score_table.append({
                        'Name': s['name'],
                        'Score': f"{s['score']}/{s['total_questions']}",
                        'Percentage': f"{s['percentage']:.1f}%"
                    })
                st.dataframe(pd.DataFrame(score_table), use_container_width=True, hide_index=True)

            # ===== Section 3: Skill Analysis =====
            st.divider()
            st.subheader("Skill Analysis")
            st.caption("Which skills does this class need to work on?")

            if report['skills']:
                # Skill performance chart
                st.plotly_chart(create_skill_chart(report['skills']), use_container_width=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Strong Skills (>=75%)**")
                    strong = [s for s in report['skills'] if s['section_performance'] >= 75]
                    if strong:
                        for s in sorted(strong, key=lambda x: -x['section_performance']):
                            st.markdown(f"- {s['skill_name']}: **{s['section_performance']:.0f}%**")
                    else:
                        st.caption("None above 75%")

                with col2:
                    st.markdown("**Skills Needing Work (<65%)**")
                    weak = [s for s in report['skills'] if s['section_performance'] < 65]
                    if weak:
                        for s in sorted(weak, key=lambda x: x['section_performance']):
                            st.error(f"{s['skill_name']}: **{s['section_performance']:.0f}%**")
                    else:
                        st.success("All skills above 65%!")

                # Detailed skill gaps
                st.divider()
                st.subheader("Which Students Need Help on Which Skills?")

                skill_gaps = calculate_class_skill_gaps(report)
                if skill_gaps:
                    # Filter to only skills with struggling students
                    gaps_with_issues = [g for g in skill_gaps if g['students_below_65'] > 0]

                    if gaps_with_issues:
                        gap_data = []
                        for gap in sorted(gaps_with_issues, key=lambda x: -x['pct_struggling']):
                            gap_data.append({
                                'Skill': gap['skill_name'],
                                'Class Score': f"{gap['class_performance']:.0f}%",
                                'Students Struggling': gap['students_below_65'],
                                'Questions': ', '.join(f"Q{q}" for q in gap['questions'])
                            })
                        st.dataframe(pd.DataFrame(gap_data), use_container_width=True, hide_index=True)

                        # Student × Skill Heatmap
                        with st.expander("View Student × Skill Heatmap"):
                            heatmap = create_class_skill_heatmap(report)
                            if heatmap:
                                st.plotly_chart(heatmap, use_container_width=True)
                                st.caption("Green = strong (>=75%), Yellow = moderate (65-74%), Red = needs support (<65%)")
                            else:
                                st.info("Individual skill data not available.")
                    else:
                        st.success("No students struggling significantly on any skill!")
            else:
                st.info("Skill data not available for this class/subject.")

        else:
            st.warning("No data available for this selection.")

    # ==================== TAB 3: STUDENT PROFILE ====================
    elif tab_selection == "Student Profile":
        st.header("Student Profile")

        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Class", data['classes'])
        with col2:
            students = get_class_students(data, selected_class)
            selected_student = st.selectbox("Select Student", students)

        if selected_student:
            student_data = get_student_data(data, selected_class, selected_student)
            overall_awards = get_student_overall_awards(data, selected_class, selected_student)

            if student_data:
                # ==================== STUDENT DATA CARD ====================
                # Consolidated view of all key metrics in one place

                # Header with name and overall award
                header_col1, header_col2 = st.columns([3, 1])
                with header_col1:
                    st.subheader(f"{selected_student}")
                    st.caption(f"Class: {selected_class}")
                with header_col2:
                    if overall_awards:
                        st.markdown(get_award_html(overall_awards['overall_award']), unsafe_allow_html=True)
                        if overall_awards['total_percentile'] > 0:
                            st.markdown(f"**Overall: {overall_awards['total_percentile']:.0f}th percentile**")

                st.divider()

                # ===== SECTION 1: National Performance Table (Color-coded) =====
                st.markdown("### National Performance")

                # Collect data for the table
                percentiles = []
                scaled_scores = []
                ats_count = 0

                subject_rows = []
                for subj_data in student_data:
                    if subj_data.get('national'):
                        nat = subj_data['national']
                        pct = nat['percentile']
                        scaled = nat['scaled_score']
                        percentiles.append(pct)
                        scaled_scores.append(scaled)
                        if nat['ats_qualified']:
                            ats_count += 1

                        subject_rows.append({
                            'Subject': subj_data['subject'],
                            'Test Score': f"{subj_data['score']}/{subj_data['total_questions']}",
                            'Test %': f"{subj_data['percentage']:.0f}%",
                            'Nat. Percentile': pct,
                            'Scaled Score': scaled,
                            'ATS': "✓" if nat['ats_qualified'] else ""
                        })
                    else:
                        subject_rows.append({
                            'Subject': subj_data['subject'],
                            'Test Score': f"{subj_data['score']}/{subj_data['total_questions']}",
                            'Test %': f"{subj_data['percentage']:.0f}%",
                            'Nat. Percentile': None,
                            'Scaled Score': None,
                            'ATS': ""
                        })

                # Add overall row
                if percentiles and overall_awards:
                    overall_pct = overall_awards['total_percentile'] if overall_awards['total_percentile'] > 0 else np.mean(percentiles)
                    overall_scaled = overall_awards.get('total_scaled_score_avg', np.mean(scaled_scores))

                    subject_rows.append({
                        'Subject': '📊 OVERALL',
                        'Test Score': '—',
                        'Test %': '—',
                        'Nat. Percentile': int(overall_pct),
                        'Scaled Score': int(overall_scaled) if overall_scaled else None,
                        'ATS': f"{ats_count} subj" if ats_count > 0 else ""
                    })

                # Create DataFrame
                perf_df = pd.DataFrame(subject_rows)

                # Function to color percentile cells
                def color_percentile(val):
                    if pd.isna(val) or val is None:
                        return 'color: #999'
                    val = int(val)
                    if val >= 85:
                        return 'background-color: #d4edda; color: #155724; font-weight: bold'
                    elif val >= 50:
                        return 'background-color: #d1ecf1; color: #0c5460; font-weight: bold'
                    elif val >= 25:
                        return 'background-color: #fff3cd; color: #856404; font-weight: bold'
                    else:
                        return 'background-color: #f8d7da; color: #721c24; font-weight: bold'

                # Style the dataframe
                styled_df = perf_df.style.applymap(
                    color_percentile,
                    subset=['Nat. Percentile']
                ).format({
                    'Nat. Percentile': lambda x: f"{int(x)}th" if pd.notna(x) and x is not None else "N/A",
                    'Scaled Score': lambda x: f"{int(x)}" if pd.notna(x) and x is not None else "N/A"
                })

                st.dataframe(
                    styled_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        'Subject': st.column_config.TextColumn(width="medium"),
                        'Test Score': st.column_config.TextColumn(width="small"),
                        'Test %': st.column_config.TextColumn(width="small"),
                        'Nat. Percentile': st.column_config.TextColumn(width="small"),
                        'Scaled Score': st.column_config.TextColumn(width="small"),
                        'ATS': st.column_config.TextColumn(width="small"),
                    }
                )

                # Legend
                st.caption("**Percentile colors:** 🟢 85th+ | 🔵 50-84th | 🟡 25-49th | 🔴 <25th  •  **Scaled Score:** 500 = National Median")

                # ===== Subject Insights =====
                if len(percentiles) >= 2:
                    # Find strongest and weakest subjects
                    subj_pct_pairs = [(subj_data['subject'], subj_data['national']['percentile'])
                                      for subj_data in student_data if subj_data.get('national')]
                    subj_pct_pairs.sort(key=lambda x: x[1], reverse=True)

                    strongest = subj_pct_pairs[0]
                    weakest = subj_pct_pairs[-1]
                    gap = strongest[1] - weakest[1]

                    if gap >= 20:
                        st.info(f"**Subject Gap:** {strongest[0]} ({strongest[1]}th) is significantly stronger than {weakest[0]} ({weakest[1]}th) — {gap} percentile points difference.")
                    elif gap >= 10:
                        st.caption(f"**Subject Gap:** {strongest[0]} ({strongest[1]}th) vs {weakest[0]} ({weakest[1]}th) — {gap} points difference.")

                st.divider()

                # ===== SECTION 2: Skills Summary by Subject =====
                st.markdown("### Skills Summary")

                for subj_data in student_data:
                    if subj_data.get('skill_performance'):
                        st.markdown(f"**{subj_data['subject']}**")

                        # Build skills table for this subject
                        skills_table = []
                        for skill_name, perf in sorted(subj_data['skill_performance'].items(),
                                                       key=lambda x: x[1]):
                            # Determine status
                            if perf >= 75:
                                status = "Strong"
                            elif perf >= 65:
                                status = "OK"
                            else:
                                status = "Needs Work"

                            # Get questions for this skill
                            skill_questions = []
                            for skill in subj_data['skills']:
                                if skill['skill_name'] == skill_name:
                                    skill_questions = skill.get('questions', [])
                                    break

                            # Find wrong questions for this skill
                            wrong_qs = []
                            if subj_data.get('question_responses'):
                                for q in skill_questions:
                                    if q <= len(subj_data['question_responses']):
                                        if subj_data['question_responses'][q - 1] == 0:
                                            wrong_qs.append(q)

                            skills_table.append({
                                'Skill': skill_name,
                                'Score': f"{perf:.0f}%",
                                'Status': status,
                                'Questions': ', '.join(f"Q{q}" for q in skill_questions[:5]) + ('...' if len(skill_questions) > 5 else ''),
                                'Missed': ', '.join(f"Q{q}" for q in wrong_qs) if wrong_qs else "-"
                            })

                        st.dataframe(
                            pd.DataFrame(skills_table),
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                'Skill': st.column_config.TextColumn(width="large"),
                                'Score': st.column_config.TextColumn(width="small"),
                                'Status': st.column_config.TextColumn(width="small"),
                                'Questions': st.column_config.TextColumn(width="medium"),
                                'Missed': st.column_config.TextColumn(width="medium"),
                            }
                        )
                        st.markdown("")  # Spacing

                # ===== SECTION 3: Quick Summary Boxes =====
                st.divider()
                st.markdown("### Key Takeaways")

                # Collect all strengths and weaknesses across subjects
                all_strengths = []
                all_weaknesses = []

                for subj_data in student_data:
                    if subj_data.get('skill_performance'):
                        subj = subj_data['subject']
                        for skill_name, perf in subj_data['skill_performance'].items():
                            if perf >= 75:
                                all_strengths.append((subj, skill_name, perf))
                            elif perf < 65:
                                all_weaknesses.append((subj, skill_name, perf))

                # Sort and display
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**Strengths (≥75%)**")
                    if all_strengths:
                        # Sort by performance descending, take top 5
                        top_strengths = sorted(all_strengths, key=lambda x: -x[2])[:5]
                        for subj, skill, perf in top_strengths:
                            st.markdown(f"- **{subj}**: {skill} ({perf:.0f}%)")
                    else:
                        st.caption("No skills at 75%+")

                with col2:
                    st.markdown("**Areas for Improvement (<65%)**")
                    if all_weaknesses:
                        # Sort by performance ascending, take top 5
                        top_weaknesses = sorted(all_weaknesses, key=lambda x: x[2])[:5]
                        for subj, skill, perf in top_weaknesses:
                            st.markdown(f"- **{subj}**: {skill} ({perf:.0f}%)")
                    else:
                        st.success("All skills at 65%+")

                # ===== SECTION 4: Detailed View (Optional) =====
                st.divider()
                with st.expander("View Detailed Charts"):
                    for subj_data in student_data:
                        if subj_data.get('skill_performance') and subj_data['skills']:
                            st.markdown(f"**{subj_data['subject']} - Skill Comparison**")
                            skill_chart = create_skill_bar_comparison(
                                subj_data['skill_performance'],
                                subj_data['skills']
                            )
                            if skill_chart:
                                st.plotly_chart(skill_chart, use_container_width=True)

            else:
                st.warning("No data available for this student.")

    # ==================== TAB 4: GROUP ANALYSIS ====================
    elif tab_selection == "Group Analysis":
        st.header("Group Analysis")
        st.markdown("Create and analyze student groups across classes for targeted skill intervention.")

        # Initialize session state for groups
        if 'saved_groups' not in st.session_state:
            st.session_state.saved_groups = load_saved_groups()

        # Subject selection
        selected_subject = st.selectbox(
            "Select Subject for Analysis",
            data['subjects'],
            key="group_subject"
        )

        # Get all students for this subject
        all_students = get_all_students_for_subject(data, selected_subject)

        # Get skills organized by class for cross-grade analysis
        skills_by_class = get_skills_by_class(data, selected_subject)

        st.divider()

        # Two columns: left for group creation, right for saved groups
        col_create, col_saved = st.columns([2, 1])

        with col_create:
            st.subheader("Create/Edit Group")

            # Multi-select for students (grouped by class)
            student_options = {s['display']: s for s in all_students}
            all_display_options = list(student_options.keys())

            # Initialize multiselect state if not exists
            if 'group_selected_students' not in st.session_state:
                st.session_state.group_selected_students = []

            # Filter to only valid options (in case subject changed)
            valid_selections = [s for s in st.session_state.group_selected_students if s in student_options]
            if valid_selections != st.session_state.group_selected_students:
                st.session_state.group_selected_students = valid_selections

            selected_displays = st.multiselect(
                "Select Students (can be from different classes)",
                options=all_display_options,
                default=st.session_state.group_selected_students,
                key="student_multiselect"
            )

            # Sync selection to session state
            st.session_state.group_selected_students = selected_displays

            # Build current group students list
            group_students = [student_options[display] for display in selected_displays]

            # Quick select helpers
            st.markdown("**Quick Select:**")
            quick_cols = st.columns(len(data['classes']))
            for i, cls in enumerate(data['classes']):
                with quick_cols[i]:
                    if st.button(f"+ {cls}", key=f"add_{cls}", use_container_width=True):
                        class_students = [s['display'] for s in all_students if s['class'] == cls]
                        # Add class students to current selection
                        new_selection = list(set(selected_displays + class_students))
                        st.session_state.group_selected_students = new_selection
                        st.rerun()

            # Save group option
            st.markdown("---")
            col_name, col_save = st.columns([3, 1])
            with col_name:
                group_name = st.text_input("Group Name (to save)", placeholder="e.g., Reading Remedial Group A")
            with col_save:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("Save Group", type="primary", disabled=not group_name or not selected_displays):
                    st.session_state.saved_groups[group_name] = {
                        'subject': selected_subject,
                        'students': selected_displays
                    }
                    save_groups(st.session_state.saved_groups)
                    st.success(f"Saved '{group_name}'!")
                    st.rerun()

        with col_saved:
            st.subheader("Saved Groups")

            # Filter saved groups by current subject
            subject_groups = {
                name: grp for name, grp in st.session_state.saved_groups.items()
                if grp.get('subject') == selected_subject
            }

            if subject_groups:
                for grp_name, grp_data in subject_groups.items():
                    with st.container():
                        col_info, col_load, col_del = st.columns([3, 1, 1])
                        with col_info:
                            st.markdown(f"**{grp_name}**")
                            st.caption(f"{len(grp_data['students'])} students")
                        with col_load:
                            if st.button("Load", key=f"load_{grp_name}"):
                                # Load saved group into selection
                                st.session_state.group_selected_students = [
                                    d for d in grp_data['students'] if d in student_options
                                ]
                                st.rerun()
                        with col_del:
                            if st.button("Del", key=f"del_{grp_name}"):
                                del st.session_state.saved_groups[grp_name]
                                save_groups(st.session_state.saved_groups)
                                st.rerun()
            else:
                st.caption(f"No saved groups for {selected_subject}")

        # ==================== GROUP ANALYSIS RESULTS ====================
        st.divider()

        if group_students and len(group_students) >= 2:
            # Analyze cross-grade skills
            skill_analysis = analyze_cross_grade_skills(group_students, skills_by_class)
            grades_in_group = skill_analysis['grades_in_group']
            common_skills = skill_analysis['common_skills']
            grade_specific_skills = skill_analysis['grade_specific_skills']

            st.subheader(f"Skill Gap Analysis ({len(group_students)} students)")

            # Show grades breakdown
            grades_str = ", ".join(grades_in_group)
            st.info(f"**Grades in group:** {grades_str}")

            # Summary metrics
            col1, col2, col3 = st.columns(3)
            percentages = [s['percentage'] for s in group_students]
            with col1:
                st.metric("Group Median", f"{np.median(percentages):.1f}%")
            with col2:
                st.metric("Group Average", f"{np.mean(percentages):.1f}%")
            with col3:
                st.metric("Range", f"{min(percentages):.0f}% - {max(percentages):.0f}%")

            # ==================== COMMON SKILLS ANALYSIS ====================
            if common_skills:
                st.markdown("### Common Skills Across All Grades")
                st.caption(f"These {len(common_skills)} skills are tested in all grades represented in this group")

                gap_df = analyze_group_skill_gaps(group_students, common_skills)
                if not gap_df.empty:
                    st.dataframe(
                        gap_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            'Group Avg': st.column_config.NumberColumn(format="%.1f%%"),
                            '% Struggling': st.column_config.ProgressColumn(
                                min_value=0, max_value=100, format="%.0f%%"
                            )
                        }
                    )

                    high_priority = gap_df[gap_df['% Struggling'] >= 50]
                    if not high_priority.empty:
                        st.warning(f"**Priority Common Skills** (50%+ struggling): {', '.join(high_priority['Skill'].tolist())}")

                # Heatmap for common skills
                with st.expander("View Common Skills Heatmap", expanded=False):
                    heatmap = create_group_skill_heatmap(
                        group_students, common_skills,
                        title="Common Skills Performance Across Group"
                    )
                    if heatmap:
                        st.plotly_chart(heatmap, use_container_width=True)
                        st.caption("Green = strong (>=75%), Yellow = moderate (65-74%), Red = needs support (<65%)")
            elif len(grades_in_group) > 1:
                st.markdown("### Common Skills Across All Grades")
                st.warning("No common skills found across the selected grades. Each grade has different skills being tested.")

            # ==================== GRADE-SPECIFIC SKILLS ANALYSIS ====================
            if grade_specific_skills:
                st.markdown("### Grade-Specific Skills")
                st.caption("These skills are unique to specific grades and only apply to students from those grades")

                for grade in sorted(grade_specific_skills.keys()):
                    specific_skills = grade_specific_skills[grade]
                    grade_students = [s for s in group_students if s['class'] == grade]

                    if specific_skills and grade_students:
                        with st.expander(f"**{grade}** - {len(specific_skills)} unique skills ({len(grade_students)} students)", expanded=False):
                            # List the unique skills
                            st.markdown("**Skills specific to this grade:**")
                            for skill in specific_skills:
                                st.markdown(f"- {skill['skill_name']}")

                            st.markdown("---")

                            # Analyze gaps for grade-specific skills
                            grade_gap_df = analyze_group_skill_gaps_by_grade(
                                group_students, specific_skills, target_grades=[grade]
                            )
                            if not grade_gap_df.empty:
                                st.dataframe(
                                    grade_gap_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        'Group Avg': st.column_config.NumberColumn(format="%.1f%%"),
                                        '% Struggling': st.column_config.ProgressColumn(
                                            min_value=0, max_value=100, format="%.0f%%"
                                        )
                                    }
                                )

                                # Heatmap for this grade
                                grade_heatmap = create_group_skill_heatmap(
                                    grade_students, specific_skills,
                                    title=f"{grade} Specific Skills Heatmap"
                                )
                                if grade_heatmap:
                                    st.plotly_chart(grade_heatmap, use_container_width=True)

            # ==================== FULL HEATMAP (ALL SKILLS BY GRADE) ====================
            if len(grades_in_group) > 1:
                st.markdown("### Full Analysis by Grade")
                st.caption("Complete skill analysis for each grade represented in the group")

                for grade in sorted(grades_in_group):
                    all_grade_skills = skill_analysis['all_skills_by_grade'].get(grade, [])
                    grade_students = [s for s in group_students if s['class'] == grade]

                    if all_grade_skills and grade_students:
                        with st.expander(f"**{grade}** - All {len(all_grade_skills)} skills ({len(grade_students)} students)", expanded=False):
                            full_gap_df = analyze_group_skill_gaps_by_grade(
                                group_students, all_grade_skills, target_grades=[grade]
                            )
                            if not full_gap_df.empty:
                                st.dataframe(
                                    full_gap_df,
                                    use_container_width=True,
                                    hide_index=True,
                                    column_config={
                                        'Group Avg': st.column_config.NumberColumn(format="%.1f%%"),
                                        '% Struggling': st.column_config.ProgressColumn(
                                            min_value=0, max_value=100, format="%.0f%%"
                                        )
                                    }
                                )

                                full_heatmap = create_group_skill_heatmap(
                                    grade_students, all_grade_skills,
                                    title=f"{grade} Complete Skills Heatmap"
                                )
                                if full_heatmap:
                                    st.plotly_chart(full_heatmap, use_container_width=True)

            # ==================== SINGLE GRADE - ORIGINAL BEHAVIOR ====================
            elif len(grades_in_group) == 1 and common_skills:
                # Single grade - show full heatmap directly
                st.markdown("### Student × Skill Heatmap")
                heatmap = create_group_skill_heatmap(group_students, common_skills)
                if heatmap:
                    st.plotly_chart(heatmap, use_container_width=True)
                    st.caption("Green = strong (>=75%), Yellow = moderate (65-74%), Red = needs support (<65%)")

            # Student list
            with st.expander("View Group Members"):
                member_df = pd.DataFrame([
                    {
                        'Name': s['name'],
                        'Class': s['class'],
                        'Score': f"{s['score']}/{s['total_questions']}",
                        'Percentage': f"{s['percentage']:.1f}%"
                    }
                    for s in sorted(group_students, key=lambda x: (-x['percentage']))
                ])
                st.dataframe(member_df, use_container_width=True, hide_index=True)

        elif group_students and len(group_students) == 1:
            st.info("Select at least 2 students to analyze as a group.")
        else:
            st.info("Select students above to create a group for analysis.")


if __name__ == "__main__":
    main()
