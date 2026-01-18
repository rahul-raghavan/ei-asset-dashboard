"""
EI ASSET Data Loader - CSV Edition

Loads student performance and skills data from CSVs and transforms
into dashboard-ready format with median-first analysis.

Parses the actual EI CSV structure:
- Student Performance: Header rows + question-by-question answers
- Skills: Skill name, questions, section/school performance
- Question-level responses: Individual student answers (correct/incorrect)
"""

import pandas as pd
import numpy as np
import json
import re
import csv
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from glob import glob


@dataclass
class StudentResult:
    """Individual student performance."""
    name: str
    score: int
    total_questions: int
    percentage: float
    question_responses: List[int] = field(default_factory=list)  # 1=correct, 0=incorrect for each Q
    skill_performance: Dict[str, float] = field(default_factory=dict)  # skill_name -> percentage


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


# ==================== NAME MATCHING ====================

# Manual override for known spelling differences between data sources
# Maps: (class_section, subject, normalized_name_in_existing) -> normalized_name_in_question_csv
# This handles cases where the same student has different spellings in different sources
NAME_SPELLING_OVERRIDES = {
    # No overrides needed - source CSV corrected to SIDDHIKSHA KATIYAR
}


def normalize_name(name: str) -> str:
    """Remove spaces and convert to uppercase for name comparison."""
    return name.upper().replace(' ', '').replace('.', '')


def get_question_csv_name(normalized_existing_name: str, class_section: str, subject: str) -> str:
    """
    Get the normalized name as it appears in the question-level CSV.

    Handles spelling differences between data sources.
    """
    override_key = (class_section, subject, normalized_existing_name)
    if override_key in NAME_SPELLING_OVERRIDES:
        return NAME_SPELLING_OVERRIDES[override_key]
    return normalized_existing_name


def build_name_matcher(existing_names: List[str], class_section: str, subject: str) -> Dict[str, str]:
    """
    Build a mapping from normalized names (no spaces) to original names (with spaces).

    Args:
        existing_names: List of names with proper spacing from existing CSVs
        class_section: Class like "3-A"
        subject: Subject like "English"

    Returns:
        Dict mapping normalized names to original names
    """
    matcher = {}
    for name in existing_names:
        normalized = normalize_name(name)
        matcher[normalized] = name

    return matcher


# ==================== QUESTION-LEVEL DATA LOADING ====================

def parse_question_level_csv(file_path: str) -> Tuple[str, str, pd.DataFrame]:
    """
    Parse a question-level CSV file from "EI Student Performance by Question CSV".

    These files have format: student_name,score,Q1,Q2,...,Q64
    - student_name: Name without spaces (e.g., "ABHIRAMDONDETI")
    - score: Raw score
    - Q1-Q64: Binary responses (1=correct, 0=incorrect)

    NOTE: Files always have 64 question columns, but actual test may have fewer questions.
    Questions beyond the actual test length are marked as 0 (not real incorrect answers).

    Returns:
        Tuple of (class_section, subject, dataframe with question responses)
    """
    # Parse filename like "3-A_English.csv"
    filename = Path(file_path).name
    parts = filename.replace('.csv', '').split('_')
    class_section = parts[0]  # "3-A"
    subject = parts[1]  # "English"

    df = pd.read_csv(file_path)

    # Get question columns (Q1, Q2, etc.)
    q_cols = [col for col in df.columns if re.match(r'^Q\d+$', col)]

    # Store question responses as list for each student
    df['question_responses'] = df[q_cols].values.tolist()
    df['class_section'] = class_section
    df['subject'] = subject

    return class_section, subject, df


def load_all_question_level_data(data_dir: str = "EI Student Performance by Question CSV") -> Dict[Tuple[str, str], pd.DataFrame]:
    """
    Load all question-level CSV files.

    Returns:
        Dict mapping (class_section, subject) to DataFrame with question responses
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"  Warning: Question-level data directory not found: {data_dir}")
        return {}

    csv_files = list(data_path.glob("*.csv"))
    if not csv_files:
        print(f"  Warning: No CSV files found in {data_dir}")
        return {}

    result = {}
    for csv_file in csv_files:
        try:
            class_section, subject, df = parse_question_level_csv(str(csv_file))
            result[(class_section, subject)] = df
            print(f"  Loaded question-level: {csv_file.name} -> {class_section} {subject} ({len(df)} students)")
        except Exception as e:
            print(f"  Warning: Failed to parse {csv_file.name}: {e}")

    return result


def calculate_student_skill_performance(
    question_responses: List[int],
    skills: List[SkillPerformance],
    total_questions: int
) -> Dict[str, float]:
    """
    Calculate a student's performance for each skill based on their question responses.

    Args:
        question_responses: List of 1/0 for each question
        skills: List of skills with their question mappings
        total_questions: Actual number of questions in the test (to ignore padding zeros)

    Returns:
        Dict mapping skill_name to percentage (0-100)
    """
    skill_perf = {}

    for skill in skills:
        # Get the questions for this skill (1-indexed in skill data)
        skill_questions = [q for q in skill.questions if q <= total_questions]

        if not skill_questions:
            continue

        # Calculate how many the student got correct
        correct = 0
        for q_num in skill_questions:
            # question_responses is 0-indexed, questions are 1-indexed
            q_idx = q_num - 1
            if q_idx < len(question_responses) and question_responses[q_idx] == 1:
                correct += 1

        # Calculate percentage
        perf = (correct / len(skill_questions)) * 100 if skill_questions else 0
        skill_perf[skill.skill_name] = round(perf, 1)

    return skill_perf


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
                       subject: str,
                       question_level_data: Optional[Dict[Tuple[str, str], pd.DataFrame]] = None) -> Optional[ClassReport]:
    """
    Build a complete class report with median-first statistics.

    Args:
        student_df: Student performance DataFrame
        skills_df: Skills mapping DataFrame
        class_section: Class identifier (e.g., "3-A")
        subject: Subject name (e.g., "English")
        question_level_data: Optional dict of question-level responses by (class, subject)

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

    # Build skills list first (needed for per-student skill calculation)
    skills = [
        SkillPerformance(
            skill_name=row['Skill Name'],
            questions=row['questions_list'],
            section_performance=float(row['Section Perf %']),
            school_performance=float(row['School Perf %'])
        )
        for _, row in class_skills.iterrows()
    ]

    # Get question-level data if available
    q_level_df = None
    name_matcher = {}
    if question_level_data and (class_section, subject) in question_level_data:
        q_level_df = question_level_data[(class_section, subject)]
        # Build name matcher from existing student names
        existing_names = class_students['student_name'].tolist()
        name_matcher = build_name_matcher(existing_names, class_section, subject)

    total_questions = int(class_students['total_questions'].iloc[0])

    # Build student results with question-level data
    students = []
    for _, row in class_students.iterrows():
        student_name = row['student_name']
        question_responses = []
        skill_performance = {}

        # Try to find question-level data for this student
        if q_level_df is not None:
            # Look up by normalized name, applying spelling overrides
            normalized_name = normalize_name(student_name)
            lookup_name = get_question_csv_name(normalized_name, class_section, subject)
            q_row = q_level_df[q_level_df['student_name'].apply(normalize_name) == lookup_name]

            if not q_row.empty:
                # Get question responses, trimmed to actual test length
                full_responses = q_row.iloc[0]['question_responses']
                question_responses = [int(r) for r in full_responses[:total_questions]]

                # Calculate per-student skill performance
                skill_performance = calculate_student_skill_performance(
                    question_responses, skills, total_questions
                )

        students.append(StudentResult(
            name=student_name,
            score=int(row['score']),
            total_questions=total_questions,
            percentage=float(row['percentage']),
            question_responses=question_responses,
            skill_performance=skill_performance
        ))

    # Calculate statistics
    stats = calculate_class_statistics(student_df, class_section, subject)

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
                      skills_data_dir: str = "EI Skills Tested By Question CSV Data",
                      question_level_dir: str = "EI Student Performance by Question CSV",
                      validate: bool = True) -> Dict[str, Any]:
    """
    Build complete school data structure for dashboard.

    This is the main entry point for data loading.

    Args:
        student_data_dir: Directory with student performance CSVs
        skills_data_dir: Directory with skills mapping CSVs
        question_level_dir: Directory with question-level response CSVs
        validate: Whether to run data validation checks

    Returns:
        Dictionary with school_info, classes, subjects, reports, and grade_medians
    """
    print("Loading student performance data...")
    student_df = load_all_student_performance(student_data_dir)

    print("\nLoading skills data...")
    skills_df = load_all_skills_data(skills_data_dir)

    print("\nLoading question-level data...")
    question_level_data = load_all_question_level_data(question_level_dir)

    # Run validation
    if validate and question_level_data:
        print("\nValidating data sources...")
        validation = validate_data_sources(student_df, question_level_data)
        if validation['warnings']:
            print(f"  Found {len(validation['warnings'])} potential issues:")
            for warning in validation['warnings']:
                print(warning)
        else:
            print("  All data sources validated successfully!")

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
            report = build_class_report(
                student_df, skills_df, class_section, subject,
                question_level_data=question_level_data
            )
            if report:
                reports.append(asdict(report))
                # Count how many students have question-level data
                students_with_q_data = sum(1 for s in report.students if s.question_responses)
                print(f"  {class_section} {subject}: {report.total_students} students, "
                      f"median={report.class_median:.1f}%, avg={report.class_average:.1f}%, "
                      f"q-level: {students_with_q_data}/{report.total_students}")

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


def validate_data_sources(
    student_df: pd.DataFrame,
    question_level_data: Dict[Tuple[str, str], pd.DataFrame]
) -> Dict[str, List[str]]:
    """
    Validate that student names match between performance CSVs and question-level CSVs.

    Returns:
        Dict with 'warnings' list of potential issues found
    """
    warnings = []

    # Check each class-subject combination
    for (class_section, subject), q_df in question_level_data.items():
        # Get students from performance data
        mask = (student_df['class_section'] == class_section) & (student_df['subject'] == subject)
        perf_students = set(student_df[mask]['student_name'].tolist())

        # Get students from question-level data (normalized names)
        q_students_normalized = set(q_df['student_name'].apply(normalize_name).tolist())

        # Normalize performance student names for comparison
        perf_students_normalized = {normalize_name(name): name for name in perf_students}

        # Find mismatches
        perf_only = set(perf_students_normalized.keys()) - q_students_normalized
        q_only = q_students_normalized - set(perf_students_normalized.keys())

        if perf_only:
            for norm_name in perf_only:
                original_name = perf_students_normalized[norm_name]
                warnings.append(
                    f"  [{class_section} {subject}] Student in performance CSV but not in question CSV: "
                    f"'{original_name}' (normalized: '{norm_name}')"
                )

        if q_only:
            for norm_name in q_only:
                warnings.append(
                    f"  [{class_section} {subject}] Student in question CSV but not in performance CSV: "
                    f"'{norm_name}'"
                )

    # Check for potential duplicate students (similar names)
    all_students = student_df.groupby('class_section')['student_name'].unique()
    for class_section, students in all_students.items():
        students = list(students)
        for i, name1 in enumerate(students):
            for name2 in students[i+1:]:
                # Check for very similar names (potential typos)
                norm1, norm2 = normalize_name(name1), normalize_name(name2)
                if norm1 != norm2:
                    # Check edit distance for similar names
                    common_len = min(len(norm1), len(norm2))
                    if common_len >= 8:  # Only check longer names
                        # Simple similarity: check if one is substring of other
                        if norm1 in norm2 or norm2 in norm1:
                            warnings.append(
                                f"  [{class_section}] Potential duplicate: '{name1}' vs '{name2}'"
                            )

    return {'warnings': warnings}


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
