"""
EI ASSET Performance Dashboard - CSV Edition

Interactive Streamlit dashboard with MEDIAN-FIRST analysis.
All primary metrics use median; averages shown as secondary reference.

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
                        'skill_performance': student.get('skill_performance', {})
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
    """Create horizontal bar chart comparing student skills to class average."""
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

    # Sort by difference (weakest first)
    combined = list(zip(skills, student_values, class_values))
    combined.sort(key=lambda x: x[1] - x[2])  # Sort by student - class diff
    skills, student_values, class_values = zip(*combined)

    # Truncate skill names for display
    truncated_skills = [truncate_label(s, 40) for s in skills]

    fig = go.Figure()

    # Class average bars (background)
    fig.add_trace(go.Bar(
        y=truncated_skills,
        x=class_values,
        name='Class Average',
        orientation='h',
        marker_color='rgba(255, 152, 0, 0.5)',
        text=[f"{v:.0f}%" for v in class_values],
        textposition='inside',
        textfont=dict(color='black', size=10),
        hovertemplate='<b>%{customdata}</b><br>Class Avg: %{x:.1f}%<extra></extra>',
        customdata=skills
    ))

    # Student bars (foreground)
    colors = [get_performance_color(v) for v in student_values]
    fig.add_trace(go.Bar(
        y=truncated_skills,
        x=student_values,
        name='Student',
        orientation='h',
        marker_color=colors,
        text=[f"{v:.0f}%" for v in student_values],
        textposition='inside',
        textfont=dict(color='white', size=10),
        hovertemplate='<b>%{customdata}</b><br>Student: %{x:.1f}%<extra></extra>',
        customdata=skills
    ))

    fig.update_layout(
        title="Skill Comparison: Student vs Class",
        xaxis_title="Performance (%)",
        xaxis=dict(range=[0, 105]),
        yaxis_title="",
        barmode='overlay',
        height=max(320, len(skills) * 48),
        margin=dict(l=260, r=40, t=60, b=40),
        yaxis=dict(tickfont=dict(size=10)),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
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
        st.header("Overview" if role_info['role'] != 'management' else "School Overview")

        stats = data['school_statistics']
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Median", f"{stats['median']:.1f}%")
            st.caption(f"Average: {stats['average']:.1f}%")
        with col2:
            st.metric("Total Students", stats['total_students'])
        with col3:
            st.metric("Total Assessments", stats['total_assessments'])
        with col4:
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
            if cls in data['grade_medians']:
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
        st.subheader("At-Risk Students (Below 60% in 2+ Subjects)")
        if len(at_risk_df) > 0:
            st.dataframe(at_risk_df, use_container_width=True, hide_index=True)
        else:
            st.success("No students currently at risk.")

        # Weak skills
        st.subheader("Skills Needing Attention (< 65%)")
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
            st.dataframe(weak_df.head(20), use_container_width=True, hide_index=True)
        else:
            st.success("All skills performing above 65%.")

    # ==================== TAB 2: CLASS ANALYSIS ====================
    elif tab_selection == "Class Analysis":
        st.header("Class Analysis")

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

            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(create_class_distribution_chart(report), use_container_width=True)
            with col2:
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

            st.subheader("Individual Student Performance")
            st.plotly_chart(create_student_bar_chart(report), use_container_width=True)

            st.subheader("Skill-wise Performance")
            if report['skills']:
                st.plotly_chart(create_skill_chart(report['skills']), use_container_width=True)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Strong Skills (>=75%)**")
                    strong = [s for s in report['skills'] if s['section_performance'] >= 75]
                    for s in strong:
                        st.markdown(f"- {s['skill_name']}: {s['section_performance']:.1f}%")
                    if not strong:
                        st.caption("None")
                with col2:
                    st.markdown("**Skills Needing Attention (<65%)**")
                    weak = [s for s in report['skills'] if s['section_performance'] < 65]
                    for s in weak:
                        st.markdown(f"- {s['skill_name']}: {s['section_performance']:.1f}%")
                    if not weak:
                        st.caption("None")

                # Class-wide skill analysis section (secondary)
                st.divider()
                st.subheader("Detailed Skill Analysis")

                # Show skill gaps analysis
                skill_gaps = calculate_class_skill_gaps(report)
                if skill_gaps:
                    st.markdown("**Skills Where Students Struggle Most:**")
                    gap_data = []
                    for gap in skill_gaps:
                        if gap['pct_struggling'] > 0:
                            gap_data.append({
                                'Skill': gap['skill_name'],
                                'Class Avg': f"{gap['class_performance']:.1f}%",
                                'Students <65%': gap['students_below_65'],
                                'Students <50%': gap['students_below_50'],
                                '% Struggling': f"{gap['pct_struggling']:.0f}%",
                                'Questions': ', '.join(f"Q{q}" for q in gap['questions'])
                            })
                    if gap_data:
                        st.dataframe(pd.DataFrame(gap_data), use_container_width=True, hide_index=True)
                    else:
                        st.success("No significant skill gaps identified!")

                # Student-by-skill heatmap (in expander to keep it secondary)
                with st.expander("View Student × Skill Heatmap"):
                    heatmap = create_class_skill_heatmap(report)
                    if heatmap:
                        st.plotly_chart(heatmap, use_container_width=True)
                        st.caption("This heatmap shows how each student performs on each skill. "
                                   "Green = strong (>=75%), Yellow = moderate (65-74%), Red = needs support (<65%)")
                    else:
                        st.info("Individual skill performance data not available for this class.")

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

            if student_data:
                st.subheader(f"{selected_student}")

                st.markdown("### Performance Summary")
                cols = st.columns(len(student_data))

                for i, subj_data in enumerate(student_data):
                    with cols[i]:
                        vs_median = subj_data['percentage'] - subj_data['class_median']

                        st.metric(
                            label=subj_data['subject'],
                            value=f"{subj_data['percentage']:.1f}%",
                            delta=f"{vs_median:+.1f}% vs Median"
                        )
                        st.caption(f"Score: {subj_data['score']}/{subj_data['total_questions']}")
                        st.caption(f"Class Median: {subj_data['class_median']:.1f}%")
                        st.caption(f"Class Avg: {subj_data['class_average']:.1f}%")

                st.divider()

                st.subheader("Multi-Subject Comparison")
                st.plotly_chart(create_spider_chart(student_data, selected_student), use_container_width=True)

                st.subheader("Performance Analysis")
                col1, col2 = st.columns(2)

                best_subj = max(student_data, key=lambda x: x['percentage'] - x['class_median'])
                worst_subj = min(student_data, key=lambda x: x['percentage'] - x['class_median'])

                with col1:
                    st.markdown("**Strongest Subject (vs Median)**")
                    delta = best_subj['percentage'] - best_subj['class_median']
                    st.success(f"{best_subj['subject']}: {best_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")

                with col2:
                    st.markdown("**Needs Focus (vs Median)**")
                    delta = worst_subj['percentage'] - worst_subj['class_median']
                    if delta < 0:
                        st.warning(f"{worst_subj['subject']}: {worst_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")
                    else:
                        st.info(f"{worst_subj['subject']}: {worst_subj['percentage']:.1f}% ({delta:+.1f}% vs median)")

                st.subheader("Subject Details & Skill Analysis")
                for subj_data in student_data:
                    with st.expander(f"{subj_data['subject']} - {subj_data['percentage']:.1f}%", expanded=False):
                        # Basic stats
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Score", f"{subj_data['score']}/{subj_data['total_questions']}")
                        with col2:
                            vs_med = subj_data['percentage'] - subj_data['class_median']
                            st.metric("vs Median", f"{vs_med:+.1f}%")
                        with col3:
                            vs_avg = subj_data['percentage'] - subj_data['class_average']
                            st.metric("vs Average", f"{vs_avg:+.1f}%")

                        # Skill-level analysis
                        if subj_data['skill_performance']:
                            st.markdown("---")
                            st.markdown("#### Skill-Level Performance")

                            # View selector for different visualizations
                            chart_type = st.radio(
                                "Visualization",
                                ["Bar Comparison", "Skill Radar", "Treemap"],
                                horizontal=True,
                                key=f"chart_type_{subj_data['subject']}"
                            )

                            if chart_type == "Bar Comparison":
                                skill_chart = create_skill_bar_comparison(
                                    subj_data['skill_performance'],
                                    subj_data['skills']
                                )
                                if skill_chart:
                                    st.plotly_chart(skill_chart, use_container_width=True)
                            elif chart_type == "Skill Radar":
                                radar_chart = create_student_skill_radar(
                                    subj_data['skill_performance'],
                                    subj_data['skills'],
                                    selected_student
                                )
                                if radar_chart:
                                    st.plotly_chart(radar_chart, use_container_width=True)
                            else:  # Treemap
                                treemap = create_skill_treemap(
                                    subj_data['skill_performance'],
                                    title=f"Skill Areas - {subj_data['subject']}"
                                )
                                if treemap:
                                    st.plotly_chart(treemap, use_container_width=True)
                                    st.caption("Size represents relative performance. Colors: Green (>=75%), Yellow (65-74%), Red (<65%)")

                            # Identify strengths and areas for improvement
                            col1, col2 = st.columns(2)
                            with col1:
                                st.markdown("**Strengths (>=75%)**")
                                strengths = [(k, v) for k, v in subj_data['skill_performance'].items() if v >= 75]
                                if strengths:
                                    for skill, perf in sorted(strengths, key=lambda x: -x[1]):
                                        st.markdown(f"- {skill}: **{perf:.0f}%**")
                                else:
                                    st.caption("None identified")

                            with col2:
                                st.markdown("**Areas for Improvement (<65%)**")
                                weak = [(k, v) for k, v in subj_data['skill_performance'].items() if v < 65]
                                if weak:
                                    for skill, perf in sorted(weak, key=lambda x: x[1]):
                                        st.markdown(f"- {skill}: **{perf:.0f}%**")
                                else:
                                    st.success("All skills above 65%!")

                            # Question-level details (use checkbox instead of nested expander)
                            if subj_data['question_responses']:
                                st.markdown("---")
                                show_q_details = st.checkbox(
                                    "Show Question-Level Details",
                                    key=f"q_details_{subj_data['subject']}"
                                )
                                if show_q_details:
                                    # Question heatmap grouped by skill
                                    q_heatmap = create_question_heatmap(
                                        subj_data['question_responses'],
                                        subj_data['skills'],
                                        subj_data['total_questions']
                                    )
                                    if q_heatmap:
                                        st.plotly_chart(q_heatmap, use_container_width=True)
                                        st.caption("Green = Correct, Red = Incorrect. Numbers show question numbers.")

                                    # Summary stats
                                    correct = sum(subj_data['question_responses'])
                                    total = len(subj_data['question_responses'])
                                    st.markdown(f"**Summary:** {correct}/{total} questions correct ({100*correct/total:.1f}%)")

                                    # List wrong questions by skill
                                    st.markdown("**Questions Incorrect by Skill:**")
                                    q_to_skill = {}
                                    for skill in subj_data['skills']:
                                        for q in skill['questions']:
                                            if q <= subj_data['total_questions']:
                                                q_to_skill[q] = skill['skill_name']

                                    wrong_by_skill = {}
                                    for i, resp in enumerate(subj_data['question_responses']):
                                        if resp == 0:
                                            q_num = i + 1
                                            skill = q_to_skill.get(q_num, "Other")
                                            if skill not in wrong_by_skill:
                                                wrong_by_skill[skill] = []
                                            wrong_by_skill[skill].append(q_num)

                                    if wrong_by_skill:
                                        for skill, questions in sorted(wrong_by_skill.items()):
                                            st.markdown(f"- **{skill}**: Q{', Q'.join(map(str, questions))}")
                                    else:
                                        st.success("All questions correct!")

                        elif subj_data['skills']:
                            # Fallback to class-level skill performance if no per-student data
                            st.markdown("---")
                            st.markdown("**Class Skill Performance** (individual question data not available)")
                            st.plotly_chart(
                                create_skill_chart(subj_data['skills'], ""),
                                use_container_width=True
                            )
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
