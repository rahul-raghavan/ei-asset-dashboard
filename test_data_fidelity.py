"""
Data Fidelity Test Suite for EI ASSET Dashboard

This test suite validates that:
1. All scores in the dashboard match the CSV source data exactly
2. All students are accounted for
3. Class/subject mappings are correct
4. No data corruption during transformation

Run with: python3 test_data_fidelity.py
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any


class DataFidelityTests:
    """Test suite for validating data fidelity between CSV and dashboard."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: int = 0
        self.failed: int = 0

    def log_error(self, message: str):
        """Log an error."""
        self.errors.append(message)
        self.failed += 1

    def log_warning(self, message: str):
        """Log a warning."""
        self.warnings.append(message)

    def log_pass(self, message: str):
        """Log a passing test."""
        self.passed += 1
        print(f"  [PASS] {message}")

    def normalize_class_section(self, raw_class: str) -> str:
        """Normalize class/section format."""
        cleaned = raw_class.strip()
        match = re.match(r'^(\d+)[\s\-]*([A-Za-z])', cleaned)
        if match:
            return f"{match.group(1)}-{match.group(2).upper()}"
        return cleaned

    def normalize_subject(self, raw_subject: str) -> str:
        """Normalize subject names."""
        subject = raw_subject.strip()
        if subject.lower() == "math":
            return "Maths"
        return subject

    def parse_csv_scores(self, csv_path: str) -> Dict[str, Dict[str, Any]]:
        """
        Parse a student performance CSV and extract scores directly.

        Returns:
            Dict mapping student_name -> {score, total_questions}
        """
        with open(csv_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        reader = csv.reader(lines)
        rows = list(reader)

        # Extract metadata
        class_section_raw = rows[0][1] if len(rows[0]) > 1 else ""
        subject_raw = rows[1][1] if len(rows[1]) > 1 else ""
        class_section = self.normalize_class_section(class_section_raw)
        subject = self.normalize_subject(subject_raw)

        # Find header row
        header_row_idx = None
        for i, row in enumerate(rows):
            if row and row[0].strip().lower() == "student name":
                header_row_idx = i
                break

        if header_row_idx is None:
            return {}

        headers = [h.strip() for h in rows[header_row_idx]]

        # Count Q columns for total_questions
        q_cols = [h for h in headers if re.match(r'^Q\d+$', h)]
        total_questions = len(q_cols)

        # Find Total Score column index
        score_col_idx = None
        for i, h in enumerate(headers):
            if h.lower() == "total score":
                score_col_idx = i
                break

        students = {}
        for row in rows[header_row_idx + 1:]:
            if not row or not row[0].strip():
                continue

            student_name = row[0].strip()

            # Skip non-student rows
            if any(x in student_name.lower() for x in ['correct answer', 'avg section', 'avg school']):
                continue

            try:
                score = int(row[score_col_idx]) if score_col_idx and score_col_idx < len(row) else 0
            except (ValueError, TypeError):
                score = 0

            students[student_name] = {
                'score': score,
                'total_questions': total_questions,
                'class_section': class_section,
                'subject': subject
            }

        return students

    def test_score_fidelity(self, csv_dir: str, json_path: str) -> bool:
        """
        Test that all scores in JSON match the CSV source exactly.

        This is the CRITICAL test - any mismatch is a data integrity failure.
        """
        print("\n" + "=" * 60)
        print("TEST: Score Fidelity (CSV vs Dashboard)")
        print("=" * 60)

        # Load dashboard data
        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        # Build lookup from dashboard data
        dashboard_scores = {}
        for report in dashboard_data['reports']:
            cls = report['class_section']
            subj = report['subject']
            for student in report['students']:
                key = (cls, subj, student['name'])
                dashboard_scores[key] = {
                    'score': student['score'],
                    'total_questions': student['total_questions'],
                    'percentage': student['percentage']
                }

        # Parse all CSV files and compare
        csv_path = Path(csv_dir)
        csv_files = list(csv_path.glob("*.csv"))

        total_students_checked = 0
        mismatches = []

        for csv_file in csv_files:
            csv_students = self.parse_csv_scores(str(csv_file))

            for student_name, csv_data in csv_students.items():
                cls = csv_data['class_section']
                subj = csv_data['subject']
                key = (cls, subj, student_name)

                total_students_checked += 1

                if key not in dashboard_scores:
                    mismatches.append(
                        f"MISSING: {student_name} ({cls} {subj}) not found in dashboard"
                    )
                    continue

                dash_data = dashboard_scores[key]

                # Check score match
                if csv_data['score'] != dash_data['score']:
                    mismatches.append(
                        f"SCORE MISMATCH: {student_name} ({cls} {subj})\n"
                        f"    CSV: {csv_data['score']}, Dashboard: {dash_data['score']}"
                    )

                # Check total_questions match
                if csv_data['total_questions'] != dash_data['total_questions']:
                    mismatches.append(
                        f"TOTAL_QUESTIONS MISMATCH: {student_name} ({cls} {subj})\n"
                        f"    CSV: {csv_data['total_questions']}, Dashboard: {dash_data['total_questions']}"
                    )

                # Verify percentage calculation
                expected_pct = round((csv_data['score'] / csv_data['total_questions']) * 100, 1)
                if abs(expected_pct - dash_data['percentage']) > 0.1:
                    mismatches.append(
                        f"PERCENTAGE MISMATCH: {student_name} ({cls} {subj})\n"
                        f"    Expected: {expected_pct}%, Dashboard: {dash_data['percentage']}%"
                    )

        if mismatches:
            print(f"\n  [FAIL] Found {len(mismatches)} data integrity issues:\n")
            for m in mismatches:
                print(f"    - {m}")
                self.log_error(m)
            return False
        else:
            self.log_pass(f"All {total_students_checked} student scores match CSV exactly")
            return True

    def test_student_count(self, csv_dir: str, json_path: str) -> bool:
        """Test that the total student count matches."""
        print("\n" + "=" * 60)
        print("TEST: Student Count")
        print("=" * 60)

        # Count students in CSVs
        csv_path = Path(csv_dir)
        csv_files = list(csv_path.glob("*.csv"))

        csv_student_count = 0
        for csv_file in csv_files:
            csv_students = self.parse_csv_scores(str(csv_file))
            csv_student_count += len(csv_students)

        # Count students in dashboard
        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        dashboard_student_count = 0
        for report in dashboard_data['reports']:
            dashboard_student_count += len(report['students'])

        if csv_student_count == dashboard_student_count:
            self.log_pass(f"Student count matches: {csv_student_count} students")
            return True
        else:
            self.log_error(
                f"Student count mismatch: CSV has {csv_student_count}, "
                f"Dashboard has {dashboard_student_count}"
            )
            return False

    def test_class_subject_coverage(self, csv_dir: str, json_path: str) -> bool:
        """Test that all class-subject combinations are covered."""
        print("\n" + "=" * 60)
        print("TEST: Class-Subject Coverage")
        print("=" * 60)

        # Get class-subject pairs from CSVs
        csv_path = Path(csv_dir)
        csv_files = list(csv_path.glob("*.csv"))

        csv_pairs = set()
        for csv_file in csv_files:
            csv_students = self.parse_csv_scores(str(csv_file))
            if csv_students:
                first_student = next(iter(csv_students.values()))
                pair = (first_student['class_section'], first_student['subject'])
                csv_pairs.add(pair)

        # Get class-subject pairs from dashboard
        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        dashboard_pairs = set()
        for report in dashboard_data['reports']:
            pair = (report['class_section'], report['subject'])
            dashboard_pairs.add(pair)

        missing_in_dashboard = csv_pairs - dashboard_pairs
        extra_in_dashboard = dashboard_pairs - csv_pairs

        success = True

        if missing_in_dashboard:
            self.log_error(f"Missing in dashboard: {missing_in_dashboard}")
            success = False

        if extra_in_dashboard:
            self.log_error(f"Extra in dashboard: {extra_in_dashboard}")
            success = False

        if success:
            self.log_pass(f"All {len(csv_pairs)} class-subject combinations present")

        return success

    def test_percentage_calculations(self, json_path: str) -> bool:
        """Test that all percentages are correctly calculated from score/total."""
        print("\n" + "=" * 60)
        print("TEST: Percentage Calculations")
        print("=" * 60)

        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        errors = []
        total_checked = 0

        for report in dashboard_data['reports']:
            for student in report['students']:
                total_checked += 1
                expected_pct = round((student['score'] / student['total_questions']) * 100, 1)

                if abs(expected_pct - student['percentage']) > 0.1:
                    errors.append(
                        f"{student['name']} ({report['class_section']} {report['subject']}): "
                        f"Expected {expected_pct}%, got {student['percentage']}%"
                    )

        if errors:
            for e in errors:
                self.log_error(e)
            return False
        else:
            self.log_pass(f"All {total_checked} percentage calculations are correct")
            return True

    def test_median_calculations(self, json_path: str) -> bool:
        """Test that median calculations are correct."""
        print("\n" + "=" * 60)
        print("TEST: Median Calculations")
        print("=" * 60)

        import statistics

        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        errors = []

        for report in dashboard_data['reports']:
            percentages = [s['percentage'] for s in report['students']]
            expected_median = statistics.median(percentages)

            if abs(expected_median - report['class_median']) > 0.1:
                errors.append(
                    f"{report['class_section']} {report['subject']}: "
                    f"Expected median {expected_median:.1f}%, got {report['class_median']:.1f}%"
                )

        if errors:
            for e in errors:
                self.log_error(e)
            return False
        else:
            self.log_pass(f"All {len(dashboard_data['reports'])} class medians are correct")
            return True

    def test_specific_students(self, json_path: str) -> bool:
        """Test specific known students for spot-check validation."""
        print("\n" + "=" * 60)
        print("TEST: Specific Student Spot Checks")
        print("=" * 60)

        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)

        # Known test cases from CSV inspection
        test_cases = [
            # (class, subject, name, expected_score, expected_total)
            ("3-A", "Maths", "MAUSAM P G", 17, 30),
            ("3-A", "Maths", "VIRAJ A ARAVIND", 5, 30),
            ("3-A", "English", "KHUSHIKA R LOMADA", 3, 35),
            ("3-A", "English", "ADIL S GUPTA", 35, 35),
        ]

        all_passed = True
        for cls, subj, name, expected_score, expected_total in test_cases:
            found = False
            for report in dashboard_data['reports']:
                if report['class_section'] == cls and report['subject'] == subj:
                    for student in report['students']:
                        if student['name'] == name:
                            found = True
                            if student['score'] != expected_score:
                                self.log_error(
                                    f"{name} ({cls} {subj}): "
                                    f"Expected score {expected_score}, got {student['score']}"
                                )
                                all_passed = False
                            elif student['total_questions'] != expected_total:
                                self.log_error(
                                    f"{name} ({cls} {subj}): "
                                    f"Expected total {expected_total}, got {student['total_questions']}"
                                )
                                all_passed = False
                            else:
                                self.log_pass(
                                    f"{name} ({cls} {subj}): {expected_score}/{expected_total} ✓"
                                )
                            break
                    break

            if not found:
                self.log_error(f"Student not found: {name} ({cls} {subj})")
                all_passed = False

        return all_passed

    def run_all_tests(self) -> bool:
        """Run all data fidelity tests."""
        print("\n" + "=" * 60)
        print("EI ASSET DATA FIDELITY TEST SUITE")
        print("=" * 60)

        csv_dir = "EI Student Performance CSV Data"
        json_path = "output/school_data.json"

        # Check files exist
        if not Path(csv_dir).exists():
            print(f"ERROR: CSV directory not found: {csv_dir}")
            return False

        if not Path(json_path).exists():
            print(f"ERROR: JSON file not found: {json_path}")
            print("Run 'python3 load_data.py' first to generate the data.")
            return False

        # Run tests
        results = []
        results.append(self.test_score_fidelity(csv_dir, json_path))
        results.append(self.test_student_count(csv_dir, json_path))
        results.append(self.test_class_subject_coverage(csv_dir, json_path))
        results.append(self.test_percentage_calculations(json_path))
        results.append(self.test_median_calculations(json_path))
        results.append(self.test_specific_students(json_path))

        # Summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        print(f"  Passed: {self.passed}")
        print(f"  Failed: {self.failed}")
        print(f"  Warnings: {len(self.warnings)}")

        if self.errors:
            print("\n  ERRORS:")
            for e in self.errors[:10]:  # Show first 10 errors
                print(f"    - {e}")
            if len(self.errors) > 10:
                print(f"    ... and {len(self.errors) - 10} more errors")

        if self.warnings:
            print("\n  WARNINGS:")
            for w in self.warnings:
                print(f"    - {w}")

        all_passed = all(results)

        if all_passed:
            print("\n" + "=" * 60)
            print("ALL TESTS PASSED - DATA INTEGRITY VERIFIED")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("TESTS FAILED - DATA INTEGRITY ISSUES FOUND")
            print("=" * 60)

        return all_passed


if __name__ == "__main__":
    tester = DataFidelityTests()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
