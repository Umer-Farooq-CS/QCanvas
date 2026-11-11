#!/usr/bin/env python3
"""
Comprehensive test runner for the QCanvas project.
This script can be run from the project root to execute all tests.
"""

import unittest
import sys
import os
import time
import argparse
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def discover_tests(pattern="test_*.py"):
    """Discover all test files matching the pattern."""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    # Discover tests in the tests directory
    tests_dir = project_root / "tests"
    if tests_dir.exists():
        start_dir = str(tests_dir)
        discovered_suite = loader.discover(start_dir, pattern=pattern)
        test_suite.addTest(discovered_suite)
    
    return test_suite


def run_tests(verbosity=2, failfast=False, pattern="test_*.py"):
    """Run all tests with specified options."""
    print("QCanvas Comprehensive Test Suite")
    print("=" * 60)
    print(f"Project root: {project_root}")
    print(f"Test pattern: {pattern}")
    print(f"Verbosity: {verbosity}")
    print(f"Fail fast: {failfast}")
    print("=" * 60)
    
    # Prefer pytest for comprehensive discovery; fallback to unittest
    try:
        import pytest  # type: ignore
        print("Using pytest discovery (tests/)...")
        # Build pytest args
        pytest_args = [
            str(project_root / "tests"),
            "-q" if verbosity <= 1 else "-vv",
        ]
        if failfast:
            pytest_args.append("-x")
        # Run pytest
        start_time = time.time()
        code = pytest.main(pytest_args)
        duration = time.time() - start_time
        print("=" * 60)
        print(f"Duration: {duration:.2f} seconds")
        return code == 0
    except Exception:
        # Fallback to unittest discovery
        print("Pytest unavailable; falling back to unittest discovery...")
        print("Discovering tests...")
        test_suite = discover_tests(pattern)
        if test_suite.countTestCases() == 0:
            print("❌ No tests found!")
            return False
        print(f"📊 Found {test_suite.countTestCases()} test cases")
        print("=" * 60)
        print("🚀 Running tests...")
        start_time = time.time()
        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            stream=sys.stdout,
            descriptions=True,
            failfast=failfast
        )
        result = runner.run(test_suite)
        end_time = time.time()
        duration = end_time - start_time
        
        # Print summary
        print("\n" + "=" * 60)
        print("Test Results Summary")
        print("=" * 60)
        print(f"Total tests: {result.testsRun}")
        print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
        print(f"Failed: {len(result.failures)}")
        print(f"Errors: {len(result.errors)}")
        print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
        print(f"Duration: {duration:.2f} seconds")
        if result.failures:
            print(f"\n❌ Failures ({len(result.failures)}):")
            for test, traceback in result.failures:
                print(f"  - {test}")
                lines = traceback.split('\n')
                for line in lines:
                    if 'AssertionError:' in line or 'FAILED' in line:
                        print(f"    {line.strip()}")
                        break
        if result.errors:
            print(f"\n💥 Errors ({len(result.errors)}):")
            for test, traceback in result.errors:
                print(f"  - {test}")
                lines = traceback.split('\n')
                for line in lines:
                    if 'Exception:' in line or 'ERROR' in line:
                        print(f"    {line.strip()}")
                        break
        print("=" * 60)
        return len(result.failures) == 0 and len(result.errors) == 0
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Print summary
    print("\n" + "=" * 60)
    print("📈 Test Results Summary")
    print("=" * 60)
    print(f"Total tests: {result.testsRun}")
    print(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failed: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print(f"Duration: {duration:.2f} seconds")
    
    if result.failures:
        print(f"\n❌ Failures ({len(result.failures)}):")
        for test, traceback in result.failures:
            print(f"  - {test}")
            # Print first line of traceback for context
            lines = traceback.split('\n')
            for line in lines:
                if 'AssertionError:' in line or 'FAILED' in line:
                    print(f"    {line.strip()}")
                    break
    
    if result.errors:
        print(f"\n💥 Errors ({len(result.errors)}):")
        for test, traceback in result.errors:
            print(f"  - {test}")
            # Print first line of traceback for context
            lines = traceback.split('\n')
            for line in lines:
                if 'Exception:' in line or 'ERROR' in line:
                    print(f"    {line.strip()}")
                    break
    
    print("=" * 60)
    
    # Return success status
    return len(result.failures) == 0 and len(result.errors) == 0


def run_specific_tests(test_paths):
    """Run specific test files or modules."""
    test_suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    
    for test_path in test_paths:
        if os.path.isfile(test_path):
            # Single test file
            module_name = test_path.replace('/', '.').replace('\\', '.').replace('.py', '')
            try:
                module = __import__(module_name, fromlist=[''])
                suite = loader.loadTestsFromModule(module)
                test_suite.addTest(suite)
                print(f"✅ Loaded {test_path}")
            except Exception as e:
                print(f"❌ Failed to load {test_path}: {e}")
        elif os.path.isdir(test_path):
            # Test directory
            suite = loader.discover(test_path, pattern="test_*.py")
            test_suite.addTest(suite)
            print(f"✅ Loaded directory {test_path}")
        else:
            print(f"❌ Path not found: {test_path}")
    
    if test_suite.countTestCases() == 0:
        print("❌ No tests found!")
        return False
    
    print(f"📊 Found {test_suite.countTestCases()} test cases")
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    return len(result.failures) == 0 and len(result.errors) == 0


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="QCanvas Test Runner")
    parser.add_argument("--pattern", "-p", default="test_*.py", 
                       help="Test file pattern (default: test_*.py)")
    parser.add_argument("--verbosity", "-v", type=int, default=2,
                       help="Test verbosity (0-2, default: 2)")
    parser.add_argument("--failfast", "-f", action="store_true",
                       help="Stop on first failure")
    parser.add_argument("--tests", "-t", nargs="+",
                       help="Run specific test files or directories")
    parser.add_argument("--category", "-c", choices=["unit", "integration", "e2e"],
                       help="Run tests for specific category")
    
    args = parser.parse_args()
    
    if args.tests:
        # Run specific tests
        success = run_specific_tests(args.tests)
    elif args.category:
        # Run tests for specific category
        category_patterns = {
            "unit": "tests/unit/test_*.py",
            "integration": "tests/integration/test_*.py",
            "e2e": "tests/e2e/test_*.py"
        }
        pattern = category_patterns.get(args.category, "test_*.py")
        success = run_tests(args.verbosity, args.failfast, pattern)
    else:
        # Run all tests
        success = run_tests(args.verbosity, args.failfast, args.pattern)
    
    if success:
        print("\nAll tests passed!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
