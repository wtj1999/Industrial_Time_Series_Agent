"""
Test script for the Industrial Time Series Agent System.

This script runs basic functionality tests to verify the system works correctly.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.schemas import (
    TaskType, TaskStage, CSVProfile, ColumnInfo, ColumnType, TaskSpecification
)
from state.session_state import SessionManager
from config.settings import settings


class TestModels(unittest.TestCase):
    """Test data models."""

    def test_column_info_creation(self):
        """Test ColumnInfo creation."""
        column_info = ColumnInfo(
            name="test_column",
            type=ColumnType.NUMERIC,
            missing_rate=0.1,
            unique_count=100,
            sample_values=[1, 2, 3, 4, 5]
        )

        self.assertEqual(column_info.name, "test_column")
        self.assertEqual(column_info.type, ColumnType.NUMERIC)
        self.assertEqual(column_info.missing_rate, 0.1)
        self.assertEqual(column_info.unique_count, 100)

    def test_task_specification_creation(self):
        """Test TaskSpecification creation."""
        task_spec = TaskSpecification(
            task_type=TaskType.PREDICTION,
            target_column="value",
            time_column="date",
            prediction_steps=25
        )

        self.assertEqual(task_spec.task_type, TaskType.PREDICTION)
        self.assertTrue(task_spec.is_complete())

    def test_task_specification_incomplete(self):
        """Test incomplete TaskSpecification."""
        task_spec = TaskSpecification(
            task_type=TaskType.PREDICTION
        )

        self.assertFalse(task_spec.is_complete())

    def test_session_state_creation(self):
        """Test SessionState creation."""
        session_state = SessionState(
            session_id="test_session"
        )

        self.assertEqual(session_state.session_id, "test_session")
        self.assertTrue(session_state.is_active)
        self.assertEqual(session_state.current_stage, TaskStage.PROFILING)

    def test_session_state_add_message(self):
        """Test adding messages to session state."""
        session_state = SessionState(session_id="test_session")

        session_state.add_message(role="user", content="Test message")

        self.assertEqual(len(session_state.dialogue_history), 1)
        self.assertEqual(session_state.dialogue_history[0].content, "Test message")


class TestSessionManager(unittest.TestCase):
    """Test session management."""

    def setUp(self):
        """Set up test fixtures."""
        self.session_manager = SessionManager()

    def test_create_session(self):
        """Test session creation."""
        session = self.session_manager.create_session("Initial query")

        self.assertIsNotNone(session)
        self.assertIsNotNone(session.session_id)
        self.assertEqual(len(session.dialogue_history), 1)

    def test_get_session(self):
        """Test retrieving session."""
        created_session = self.session_manager.create_session()
        retrieved_session = self.session_manager.get_session(created_session.session_id)

        self.assertEqual(created_session.session_id, retrieved_session.session_id)

    def test_update_session(self):
        """Test updating session."""
        session = self.session_manager.create_session()
        updated_session = self.session_manager.update_session(
            session.session_id,
            current_task=TaskType.PREDICTION
        )

        self.assertEqual(updated_session.current_task, TaskType.PREDICTION)

    def test_add_dialogue_message(self):
        """Test adding dialogue messages."""
        session = self.session_manager.create_session()
        updated_session = self.session_manager.add_dialogue_message(
            session.session_id,
            role="user",
            content="Test query"
        )

        self.assertEqual(len(updated_session.dialogue_history), 2)  # Initial + new

    def test_clear_session(self):
        """Test clearing session."""
        session = self.session_manager.create_session()
        result = self.session_manager.clear_session(session.session_id)

        self.assertTrue(result)
        retrieved_session = self.session_manager.get_session(session.session_id)
        self.assertFalse(retrieved_session.is_active)


class TestTools(unittest.TestCase):
    """Test tool functions."""

    def test_column_type_detection(self):
        """Test column type detection."""
        from tools.data_tools import _detect_column_type
        import pandas as pd

        # Numeric column
        numeric_series = pd.Series([1, 2, 3, 4, 5])
        col_type = _detect_column_type(numeric_series)
        self.assertEqual(col_type, ColumnType.NUMERIC)

        # Categorical column
        categorical_series = pd.Series(['A', 'B', 'C', 'A', 'B'])
        col_type = _detect_column_type(categorical_series)
        self.assertEqual(col_type, ColumnType.CATEGORICAL)

    def test_validate_file_path(self):
        """Test file path validation."""
        from utils.helpers import validate_file_path

        # Valid path (create a test file first)
        test_file = "data/test_temp.csv"
        os.makedirs("data", exist_ok=True)
        with open(test_file, 'w') as f:
            f.write("test,data\n1,2\n")

        is_valid, error = validate_file_path(test_file)
        self.assertTrue(is_valid)
        self.assertIsNone(error)

        # Clean up
        os.remove(test_file)

        # Invalid path
        is_valid, error = validate_file_path("nonexistent.csv")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)


class TestAgents(unittest.TestCase):
    """Test agent functionality."""

    def test_parser_agent_intent_identification(self):
        """Test intent identification."""
        from agents.parser_agent_v0 import ParserAgent

        parser = ParserAgent()

        # Test prediction intent
        intent, confidence = parser.identify_intent("预测未来25步")
        self.assertEqual(intent, TaskType.PREDICTION)

        # Test anomaly detection intent
        intent, confidence = parser.identify_intent("检测异常点")
        self.assertEqual(intent, TaskType.ANOMALY_DETECTION)

    def test_parser_agent_parameter_extraction(self):
        """Test parameter extraction."""
        from agents.parser_agent_v0 import ParserAgent

        parser = ParserAgent()

        # Create a mock CSV profile
        mock_profile = CSVProfile(
            file_name="test.csv",
            file_path="data/test.csv",
            dataset_id="test_id",
            total_rows=100,
            total_columns=5,
            columns={},
            time_column_candidates=["date"],
            target_column_candidates=["value"]
        )

        # Test parameter extraction
        params = parser.extract_parameters(
            "预测value列25步",
            mock_profile,
            None
        )

        self.assertIn('target_column', params)
        self.assertIn('prediction_steps', params)

    def test_profile_agent_suggestions(self):
        """Test profile agent task suggestions."""
        from agents.profile_agent import ProfileAgent

        profile_agent = ProfileAgent()

        # Create a mock profile with time and target columns
        mock_profile = CSVProfile(
            file_name="test.csv",
            file_path="data/test.csv",
            dataset_id="test_id",
            total_rows=100,
            total_columns=5,
            columns={},
            time_column_candidates=["date"],
            target_column_candidates=["value"],
            numeric_columns=["value", "temp"],
            categorical_columns=["category"]
        )

        suggestions = profile_agent.suggest_analysis_tasks(mock_profile)

        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any(s['task_type'] == 'prediction' for s in suggestions))


class TestConfiguration(unittest.TestCase):
    """Test configuration settings."""

    def test_settings_loading(self):
        """Test settings are loaded correctly."""
        self.assertIsNotNone(settings)
        self.assertEqual(settings.app_name, "Industrial Time Series Agent System")
        self.assertIsNotNone(settings.version)

    def test_llm_configuration(self):
        """Test LLM configuration."""
        self.assertIsNotNone(settings.llm)
        self.assertEqual(settings.llm.provider, "openai")  # Default value


class TestUtilities(unittest.TestCase):
    """Test utility functions."""

    def test_format_response(self):
        """Test response formatting."""
        from utils.helpers import format_response

        response = format_response(
            success=True,
            message="Test message",
            data={"key": "value"}
        )

        self.assertTrue(response['success'])
        self.assertEqual(response['message'], "Test message")
        self.assertEqual(response['data']['key'], "value")

    def test_truncate_text(self):
        """Test text truncation."""
        from utils.helpers import truncate_text

        long_text = "This is a very long text that should be truncated"
        truncated = truncate_text(long_text, max_length=20)

        self.assertLessEqual(len(truncated), 23)  # 20 + "..."

    def test_calculate_percentile(self):
        """Test percentile calculation."""
        from utils.helpers import calculate_percentile

        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        percentile_50 = calculate_percentile(values, 50)

        self.assertEqual(percentile_50, 5.5)


def run_basic_functionality_test():
    """Run basic functionality test."""
    print("=" * 60)
    print("基本功能测试")
    print("=" * 60)
    print()

    try:
        # Test imports
        print("1. 测试模块导入...")
        from main import IndustrialTimeSeriesAgent
        from state.session_state import SessionManager
        from agents.orchestrator_agent import OrchestratorAgent
        print("   ✅ 所有模块导入成功")

        # Test system initialization
        print("\n2. 测试系统初始化...")
        agent = IndustrialTimeSeriesAgent()
        print("   ✅ 系统初始化成功")

        # Test session creation
        print("\n3. 测试会话创建...")
        session_id = agent.create_new_session("测试查询")
        print(f"   ✅ 会话创建成功: {session_id}")

        # Test session info
        print("\n4. 测试会话信息获取...")
        info = agent.get_session_info(session_id)
        if info:
            print(f"   ✅ 会话信息获取成功")
            print(f"   Session ID: {info['session_id']}")
            print(f"   对话轮数: {info['dialogue_turns']}")

        # Test system status
        print("\n5. 测试系统状态...")
        status = agent.get_system_status()
        print(f"   ✅ 系统状态获取成功")
        print(f"   系统名称: {status['system']['name']}")
        print(f"   活动会话: {status['sessions']['active_count']}")

        print()
        print("=" * 60)
        print("✅ 基本功能测试通过！")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("工业时间序列多智能体系统 - 测试套件")
    print("=" * 60)
    print()

    # Run basic functionality test
    if not run_basic_functionality_test():
        print("\n基本功能测试失败，跳过单元测试。")
        return

    print("\n按回车键继续运行单元测试...")
    input()

    # Run unit tests
    print("\n运行单元测试...")
    unittest.main(argv=[''], verbosity=2, exit=True)


if __name__ == '__main__':
    main()
