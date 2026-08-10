"""
Example usage of the Industrial Time Series Agent System.

This script demonstrates how to use the multi-agent system for various time series analysis tasks.
"""

import os
import sys

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import IndustrialTimeSeriesAgent


def example_basic_usage():
    """Basic usage example."""
    print("=== 基础使用示例 ===")
    print()

    # Initialize the agent system
    agent = IndustrialTimeSeriesAgent()

    # Example 1: Simple prediction query
    print("1. 预测查询示例:")
    result = agent.process_query(
        query="预测未来25步",
        file_path="data/sample_data.csv"
    )

    if result['success']:
        print(f"✅ {result['response']}")
        print(f"Session ID: {result['session_id']}")
    else:
        print(f"❌ Error: {result.get('error')}")

    print()


def example_multi_turn_conversation():
    """Multi-turn conversation example."""
    print("=== 多轮对话示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    # Create a new session
    session_id = agent.create_new_session()
    print(f"Created session: {session_id}")

    # First query
    print("\n1. 第一轮查询:")
    result = agent.process_query(
        query="分析销售数据的趋势",
        file_path="data/sales_data.csv",
        session_id=session_id
    )

    if result['success']:
        print(f"Response: {result['response']}")

    # Follow-up query
    print("\n2. 追问查询:")
    result = agent.continue_session(
        session_id=session_id,
        query="再详细解释一下异常点"
    )

    if result['success']:
        print(f"Response: {result['response']}")

    # Get session history
    print("\n3. 对话历史:")
    history = agent.get_session_history(session_id, limit=10)
    if history['success']:
        print(f"Total messages: {history['total_messages']}")
        for msg in history['history'][-4:]:  # Show last 4 messages
            print(f"  {msg['role']}: {msg['content'][:50]}...")

    print()


def example_anomaly_detection():
    """Anomaly detection example."""
    print("=== 异常检测示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    # Anomaly detection query
    print("1. 异常检测查询:")
    result = agent.process_query(
        query="检测传感器数据中的异常点",
        file_path="data/sensor_data.csv"
    )

    if result['success']:
        print(f"✅ {result['response']}")

        if result.get('followup_suggestions'):
            print("\n建议的后续操作:")
            for suggestion in result['followup_suggestions']:
                print(f"  • {suggestion}")

    print()


def example_comprehensive_analysis():
    """Comprehensive analysis example."""
    print("=== 综合分析示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    session_id = agent.create_new_session()

    # Step 1: Data profiling
    print("1. 数据画像:")
    result = agent.process_query(
        query="分析这个数据集",
        file_path="data/industrial_data.csv",
        session_id=session_id
    )

    if result['success']:
        print(f"✅ {result['response']}")

    # Step 2: Prediction
    print("\n2. 预测分析:")
    result = agent.continue_session(
        session_id=session_id,
        query="预测目标变量未来25步"
    )

    if result['success']:
        print(f"✅ {result['response']}")

    # Step 3: Anomaly detection
    print("\n3. 异常检测:")
    result = agent.continue_session(
        session_id=session_id,
        query="检查是否有异常点"
    )

    if result['success']:
        print(f"✅ {result['response']}")

    # Step 4: Generate report
    print("\n4. 生成报告:")
    result = agent.continue_session(
        session_id=session_id,
        query="生成综合分析报告"
    )

    if result['success']:
        print(f"✅ {result['response']}")

    # Get final session info
    print("\n5. 会话信息:")
    info = agent.get_session_info(session_id)
    if info:
        print(f"  Session ID: {info['session_id']}")
        print(f"  Current Task: {info['current_task']}")
        print(f"  Dialogue Turns: {info['dialogue_turns']}")
        print(f"  Analysis Artifacts: {info['analysis_artifacts_count']}")

    print()


def example_session_management():
    """Session management example."""
    print("=== 会话管理示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    # Create multiple sessions
    print("1. 创建多个会话:")
    session1 = agent.create_new_session("初始查询 1")
    session2 = agent.create_new_session("初始查询 2")

    print(f"  Session 1: {session1}")
    print(f"  Session 2: {session2}")

    # Get system status
    print("\n2. 系统状态:")
    status = agent.get_system_status()
    print(f"  Active Sessions: {status['sessions']['active_count']}")
    print(f"  System Version: {status['system']['version']}")

    # Get available tasks
    print("\n3. 可用任务:")
    # First process a file to get profile
    agent.process_query(
        query="分析数据",
        file_path="data/sample_data.csv",
        session_id=session1
    )

    tasks = agent.get_available_tasks(session1)
    if tasks['success']:
        print(f"  Available Tasks: {', '.join(tasks['available_tasks'])}")

    # Reset session task
    print("\n4. 重置会话任务:")
    reset_result = agent.reset_session_task(session1)
    if reset_result['success']:
        print(f"  ✅ {reset_result['message']}")

    # Cleanup expired sessions
    print("\n5. 清理过期会话:")
    cleanup_result = agent.cleanup_expired_sessions()
    if cleanup_result['success']:
        print(f"  ✅ {cleanup_result['message']}")

    print()


def example_error_handling():
    """Error handling example."""
    print("=== 错误处理示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    # Example 1: Invalid file path
    print("1. 无效文件路径:")
    result = agent.process_query(
        query="预测数据",
        file_path="data/nonexistent.csv"
    )

    if not result['success']:
        print(f"  ❌ Error: {result.get('error')}")

    # Example 2: Invalid session ID
    print("\n2. 无效会话 ID:")
    result = agent.get_session_info("invalid_session_id")
    if result is None:
        print(f"  ❌ Session not found")

    # Example 3: Missing parameters
    print("\n3. 缺少参数:")
    session_id = agent.create_new_session()
    result = agent.process_query(
        query="预测",  # Missing target column info
        session_id=session_id
    )

    if not result['success'] and result.get('needs_clarification'):
        print(f"  ❌ Needs clarification:")
        for question in result.get('questions', []):
            print(f"    - {question}")

    print()


def example_parameter_modification():
    """Parameter modification example."""
    print("=== 参数修改示例 ===")
    print()

    agent = IndustrialTimeSeriesAgent()

    # Initial prediction
    print("1. 初始预测 (25步):")
    session_id = agent.create_new_session()
    result = agent.process_query(
        query="预测未来25步",
        file_path="data/sample_data.csv",
        session_id=session_id
    )

    if result['success']:
        print(f"  ✅ {result['response']}")

    # Modify prediction steps
    print("\n2. 修改预测步数 (50步):")
    result = agent.continue_session(
        session_id=session_id,
        query="把预测步数改成50"
    )

    if result['success']:
        print(f"  ✅ {result['response']}")

    # Change target column
    print("\n3. 更改目标列:")
    result = agent.continue_session(
        session_id=session_id,
        query="改用另一列进行预测"
    )

    if result['success']:
        print(f"  ✅ {result['response']}")

    print()


def main():
    """Run all examples."""
    print("=" * 60)
    print("工业时间序列多智能体系统 - 使用示例")
    print("=" * 60)
    print()

    try:
        # Run examples
        example_basic_usage()
        # example_multi_turn_conversation()
        # example_anomaly_detection()
        # example_comprehensive_analysis()
        # example_session_management()
        # example_error_handling()
        # example_parameter_modification()

        print("=" * 60)
        print("示例运行完成！")
        print("=" * 60)

    except Exception as e:
        print(f"运行示例时出错: {str(e)}")
        print("请确保:")
        print("1. 已安装所有依赖 (pip install -r requirements.txt)")
        print("2. 数据文件存在在 data/ 目录下")
        print("3. 环境变量已正确配置")


if __name__ == '__main__':
    main()
