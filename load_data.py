"""
EI ASSET Data Loader - CSV Edition

Loads student performance and skills data from CSVs and transforms
into dashboard-ready format with median-first analysis.

Parses the actual EI CSV structure:
- Student Performance: Header rows + question-by-question answers
- Skills: Skill name, questions, section/school performance
"""

import pandas as pd
import numpy as np
import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from glob import glob


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


def normalize_class_section(raw_class: str) -> str:
    """
    Normalize class/section to standard format: "3-A", "4-A", etc.

    Handles variations like:
    - "3 A" -> "3-A"
    - "3-A A" -> "3-A"
    - "8 A" -> "8-A"
    """
    # Remove extra whitespace
    cleaned = raw_class.strip()

    # Pattern: extract grade number and section letter
    # Handles "3 A", "3-A", "3-A A", etc.
    match = re.match(r'^(\d+)[\s\-]*([A-Za-z])', cleaned)
    if match:
        grade = match.group(1)
        section = match.group(2).upper()
        return f"{grade}-{section}"

    # Fallback: return cleaned version
    return cleaned


def normalize_subject(raw_subject: str) -> str:
    """
    Normalize subject names to standard format.

    Handles variations like:
    - "Maths" -> "Maths"
    - "Math" -> "Maths"
    """
    subject = raw_subject.strip()
    if subject.lower() == "math":
        return "Maths"
    return subject


def parse_student_performance_csv(file_path: str) -> Tuple[str, str, pd.DataFrame]:
    """
    Parse a student performance CSV file with EI's actual structure.

    IMPORTANT: Uses the "Total Score" column from CSV directly as the authoritative
    score. We do NOT recalculate from answers because:
    1. The CSV score is what EI officially calculated
    2. Some questions may have different weightings
    3. The answer key in CSV may not reflect actual grading

    Structure:
    - Row 0: Class/Section header
    - Row 1: Subject header
    - Row 2: Month & Year header
    - Row 3: Empty
    - Row 4: Column headers (Student Name, Total Score, Q1, Q2, ...)
    - Row 5: Correct Answer row
    - Rows 6+: Student data
    - Last row(s): Avg Section/School Perf %

    Returns:
        Tuple of (class_section, subject, student_dataframe)
    """
    # Read raw to get metadata
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Parse metadata from first few lines
    import csv
    reader = csv.reader(lines)
    rows = list(reader)

    # Extract class and subject from header rows
    class_section_raw = rows[0][1] if len(rows[0]) > 1 else ""
    subject_raw = rows[1][1] if len(rows[1]) > 1 else ""

    class_section = normalize_class_section(class_section_raw)
    subject = normalize_subject(subject_raw)

    # Find the header row (contains "Student Name")
    header_row_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "student name":
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError(f"Could not find header row in {file_path}")

    # Read as DataFrame starting from header row
    df = pd.read_csv(file_path, skiprows=header_row_idx, encoding='utf-8')

    # Clean column names
    df.columns = df.columns.str.strip()

    # Remove the "Correct Answer" row and any summary rows
    df = df[~df['Student Name'].str.contains('Correct Answer|Avg Section|Avg School',
                                              case=False, na=False)]

    # Remove any rows where Student Name is empty or NaN
    df = df[df['Student Name'].notna() & (df['Student Name'].str.strip() != '')]

    # Identify question columns (Q1, Q2, etc.) to get total_questions count
    q_cols = [col for col in df.columns if re.match(r'^Q\d+$', col)]
    total_questions = len(q_cols)

    # Use "Total Score" column directly from CSV - this is the authoritative score
    student_data = []
    for _, row in df.iterrows():
        student_name = str(row['Student Name']).strip()

        # Get score directly from CSV's "Total Score" column
        raw_score = row.get('Total Score', 0)
        try:
            score = int(raw_score)
        except (ValueError, TypeError):
            # If score is not a valid integer, set to 0
            score = 0

        # Calculate percentage based on CSV score and total questions
        percentage = round((score / total_questions) * 100, 1) if total_questions > 0 else 0.0

        student_data.append({
            'student_name': student_name,
            'score': score,
            'total_questions': total_questions,
            'percentage': percentage
        })

    result_df = pd.DataFrame(student_data)
    result_df['class_section'] = class_section
    result_df['subject'] = subject

    return class_section, subject, result_df


def parse_skills_csv(file_path: str) -> Tuple[str, str, pd.DataFrame]:
    """
    Parse a skills CSV file with EI's actual structure.

    Structure:
    - Row 0: Class/Section header
    - Row 1: Subject header
    - Row 2: Month & Year header
    - Row 3: Empty
    - Row 4: Column headers (Skill Name, Questions, Section Perf %, School Perf %)
    - Rows 5+: Skill data

    Returns:
        Tuple of (class_section, subject, skills_dataframe)
    """
    # Read raw to get metadata
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    import csv
    reader = csv.reader(lines)
    rows = list(reader)

    # Extract class and subject from header rows
    class_section_raw = rows[0][1] if len(rows[0]) > 1 else ""
    subject_raw = rows[1][1] if len(rows[1]) > 1 else ""

    class_section = normalize_class_section(class_section_raw)
    subject = normalize_subject(subject_raw)

    # Find the header row (contains "Skill Name")
    header_row_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == "skill name":
            header_row_idx = i
            break

    if header_row_idx is None:
        raise ValueError(f"Could not find header row in {file_path}")

    # Read as DataFrame starting from header row
    df = pd.read_csv(file_path, skiprows=header_row_idx, encoding='utf-8')

    # Clean column names
    df.columns = df.columns.str.strip()

    # Remove any rows where Skill Name is empty
    df = df[df['Skill Name'].notna() & (df['Skill Name'].str.strip() != '')]

    # Parse questions string to list of integers
    def parse_questions(q_str):
        if pd.isna(q_str):
            return []
        return [int(q.strip()) for q in str(q_str).split(',') if q.strip().isdigit()]

    df['questions_list'] = df['Questions'].apply(parse_questions)

    # Ensure numeric columns
    df['Section Perf %'] = pd.to_numeric(df['Section Perf %'], errors='coerce').fillna(0)
    df['School Perf %'] = pd.to_numeric(df['School Perf %'], errors='coerce').fillna(0)

    df['class_section'] = class_section
    df['subject'] = subject

    return class_section, subject, df


def load_all_student_performance(data_dir: str = "EI Student Performance CSV Data") -> pd.DataFrame:
    """
    Load all student performance CSV files from the data directory.

    Returns:
        Combined DataFrame with all student data
    """
    data_path = Path(data_dir)
    csv_files = list(data_path.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    all_data = []
    for csv_file in csv_files:
        try:
            class_section, subject, df = parse_student_performance_csv(str(csv_file))
            all_data.append(df)
            print(f"  Loaded: {csv_file.name} -> {class_section} {subject} ({len(df)} students)")
        except Exception as e:
            print(f"  Warning: Failed to parse {csv_file.name}: {e}")

    if not all_data:
        raise ValueError("No student performance data could be loaded")

    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df


def load_all_skills_data(data_dir: str = "EI Skills Tested By Question CSV Data") -> pd.DataFrame:
    """
    Load all skills CSV files from the data directory.

    Returns:
        Combined DataFrame with all skills data
    """
    data_path = Path(data_dir)
    csv_files = list(data_path.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    all_data = []
    for csv_file in csv_files:
        try:
            class_section, subject, df = parse_skills_csv(str(csv_file))
            all_data.append(df)
            print(f"  Loaded: {csv_file.name} -> {class_section} {subject} ({len(df)} skills)")
        except Exception as e:
            print(f"  Warning: Failed to parse {csv_file.name}: {e}")

    if not all_data:
        raise ValueError("No skills data could be loaded")

    combined_df = pd.concat(all_data, ignore_index=True)
    return combined_df


def calculate_class_statistics(student_df: pd.DataFrame,
                                class_section: str,
                                subject: str) -> Optional[Dict[str, Any]]:
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
        'average': float(round(class_data.mean(), 1)),  # Secondary metric
        'min': float(class_data.min()),
        'max': float(class_data.max()),
        'q1': float(class_data.quantile(0.25)),         # First quartile
        'q3': float(class_data.quantile(0.75)),         # Third quartile
        'std': float(round(class_data.std(), 1)) if len(class_data) > 1 else 0.0,
        'count': int(len(class_data)),
        'below_median_count': int((class_data < class_data.median()).sum()),
        'below_60_count': int((class_data < 60).sum())  # At-risk threshold
    }


def build_class_report(student_df: pd.DataFrame,
                       skills_df: pd.DataFrame,
                       class_section: str,
                       subject: str) -> Optional[ClassReport]:
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
            skill_name=row['Skill Name'],
            questions=row['questions_list'],
            section_performance=float(row['Section Perf %']),
            school_performance=float(row['School Perf %'])
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


def sort_class_sections(classes: List[str]) -> List[str]:
    """
    Sort class sections by grade number, then by section letter.
    E.g., ["3-A", "4-A", "5-A", "6-A", "7-A", "8-A"]
    """
    def sort_key(cls):
        match = re.match(r'^(\d+)-([A-Z])$', cls)
        if match:
            return (int(match.group(1)), match.group(2))
        return (999, cls)  # Fallback for unexpected formats

    return sorted(classes, key=sort_key)


def build_school_data(student_data_dir: str = "EI Student Performance CSV Data",
                      skills_data_dir: str = "EI Skills Tested By Question CSV Data") -> Dict[str, Any]:
    """
    Build complete school data structure for dashboard.

    This is the main entry point for data loading.

    Returns:
        Dictionary with school_info, classes, subjects, reports, and grade_medians
    """
    print("Loading student performance data...")
    student_df = load_all_student_performance(student_data_dir)

    print("\nLoading skills data...")
    skills_df = load_all_skills_data(skills_data_dir)

    # Get unique classes and subjects
    classes = sort_class_sections(student_df['class_section'].unique().tolist())
    subjects = sorted(student_df['subject'].unique().tolist())

    print(f"\nFound {len(classes)} classes: {classes}")
    print(f"Found {len(subjects)} subjects: {subjects}")

    # Build reports for each class-subject combination
    print("\nBuilding class reports...")
    reports = []
    for class_section in classes:
        for subject in subjects:
            report = build_class_report(student_df, skills_df, class_section, subject)
            if report:
                reports.append(asdict(report))
                print(f"  {class_section} {subject}: {report.total_students} students, "
                      f"median={report.class_median:.1f}%, avg={report.class_average:.1f}%")

    # Calculate grade-level medians (across all subjects per grade)
    grade_medians = {}
    for class_section in classes:
        class_data = student_df[student_df['class_section'] == class_section]['percentage']
        grade_medians[class_section] = {
            'overall_median': float(class_data.median()),
            'overall_average': float(round(class_data.mean(), 1)),
            'by_subject': {}
        }
        for subject in subjects:
            mask = (student_df['class_section'] == class_section) & \
                   (student_df['subject'] == subject)
            subj_data = student_df[mask]['percentage']
            if len(subj_data) > 0:
                grade_medians[class_section]['by_subject'][subject] = {
                    'median': float(subj_data.median()),
                    'average': float(round(subj_data.mean(), 1))
                }

    # Calculate school-wide medians
    school_median = float(student_df['percentage'].median())
    school_average = float(round(student_df['percentage'].mean(), 1))

    # Count unique students (by name within each class)
    unique_students = student_df.groupby('class_section')['student_name'].nunique().sum()

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
            'total_students': int(unique_students),
            'total_assessments': len(student_df)
        }
    }


def save_school_data(data: Dict[str, Any],
                     output_path: str = "output/school_data.json") -> None:
    """Save processed school data to JSON for dashboard consumption."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nSchool data saved to {output_path}")


def load_school_data(json_path: str = "output/school_data.json") -> Dict[str, Any]:
    """Load processed school data from JSON."""
    with open(json_path, 'r') as f:
        return json.load(f)


# CLI entry point
if __name__ == "__main__":
    print("=" * 60)
    print("EI ASSET Data Loader")
    print("=" * 60)

    data = build_school_data()
    save_school_data(data)

    print("\n" + "=" * 60)
    print("Data Summary")
    print("=" * 60)
    print(f"  Classes: {data['classes']}")
    print(f"  Subjects: {data['subjects']}")
    print(f"  Total Reports: {len(data['reports'])}")
    print(f"  Total Students: {data['school_statistics']['total_students']}")
    print(f"  Total Assessments: {data['school_statistics']['total_assessments']}")
    print(f"  School Median: {data['school_statistics']['median']:.1f}%")
    print(f"  School Average: {data['school_statistics']['average']:.1f}%")
