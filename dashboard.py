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
        name=student_name,
        line_color='#1976d2',
        fillcolor='rgba(25, 118, 210, 0.3)'
    ))

    fig.add_trace(go.Scatterpolar(
        r=class_medians + [class_medians[0]],
        theta=subjects + [subjects[0]],
        fill='toself',
        name='Class Median',
        line_color='#388e3c',
        line_width=3,
        fillcolor='rgba(56, 142, 60, 0.2)'
    ))

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
        xaxis=dict(range=[0, 105]),
        height=max(300, len(skills) * 40),
        margin=dict(l=250)
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
        yaxis=dict(range=[0, 105]),
        height=400,
        showlegend=False
    )

    return fig


def create_student_bar_chart(report: dict) -> go.Figure:
    """Create bar chart of student performance with MEDIAN reference line."""
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

    fig.add_hline(
        y=report['class_median'],
        line_dash="solid",
        line_color="#388e3c",
        line_width=3,
        annotation_text=f"Median: {report['class_median']:.1f}%",
        annotation_position="right"
    )

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
        yaxis=dict(range=[0, 110]),
        xaxis_tickangle=-45,
        height=450
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

    fig.update_layout(
        title="Performance Heatmap (by Median %)",
        height=max(300, len(classes) * 50)
    )

    return fig, df


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
        ["School Overview", "Class Analysis", "Student Profile"]
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

                st.subheader("Subject Details")
                for subj_data in student_data:
                    with st.expander(f"{subj_data['subject']} - {subj_data['percentage']:.1f}%"):
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
