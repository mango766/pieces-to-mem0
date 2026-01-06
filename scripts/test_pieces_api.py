#!/usr/bin/env python3
"""
Pieces OS API 测试脚本

用于验证 Pieces OS 连接和 API 功能。
运行前请确保 Pieces OS 已安装并运行。

使用方法:
    python scripts/test_pieces_api.py
"""

import sys
from datetime import datetime


def check_pieces_running():
    """检查 Pieces OS 是否运行"""
    print("=" * 60)
    print("1. 检查 Pieces OS 连接状态")
    print("=" * 60)
    
    try:
        from pieces_os_client.wrapper import PiecesClient
        
        client = PiecesClient()
        
        if client.is_pieces_running():
            print(f"✅ Pieces OS 正在运行")
            print(f"   版本: {client.version}")
            print(f"   端口: {client.port}")
            client.close()
            return True
        else:
            print("❌ Pieces OS 未运行")
            print("   请启动 Pieces Desktop App")
            return False
            
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("   请确保 Pieces OS 已安装并运行")
        return False


def test_health_api():
    """测试健康检查 API"""
    print("\n" + "=" * 60)
    print("2. 测试健康检查 API")
    print("=" * 60)
    
    try:
        import pieces_os_client
        from pieces_os_client.api.well_known_api import WellKnownApi
        
        config = pieces_os_client.Configuration(host="http://localhost:39300")
        
        with pieces_os_client.ApiClient(config) as api_client:
            api = WellKnownApi(api_client)
            response = api.get_well_known_health()
            print(f"✅ 健康检查: {response}")
            return True
            
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False


def test_assets_api():
    """测试资源 API"""
    print("\n" + "=" * 60)
    print("3. 测试资源 (Assets) API")
    print("=" * 60)
    
    try:
        from pieces_os_client.wrapper import PiecesClient
        
        client = PiecesClient()
        assets = list(client.assets())
        
        print(f"✅ 获取到 {len(assets)} 个代码片段")
        
        if assets:
            print("\n   最近的代码片段:")
            for i, asset in enumerate(assets[:3]):
                name = asset.name or "(未命名)"
                print(f"   {i+1}. {name[:50]}...")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ 资源 API 测试失败: {e}")
        return False


def test_workstream_events_api():
    """测试工作流事件 API"""
    print("\n" + "=" * 60)
    print("4. 测试工作流事件 (Workstream Events) API")
    print("=" * 60)
    
    try:
        import pieces_os_client
        from pieces_os_client.api.workstream_events_api import WorkstreamEventsApi
        
        config = pieces_os_client.Configuration(host="http://localhost:39300")
        
        with pieces_os_client.ApiClient(config) as api_client:
            api = WorkstreamEventsApi(api_client)
            events = api.workstream_events_snapshot()
            
            if hasattr(events, 'iterable') and events.iterable:
                event_list = list(events.iterable)
                print(f"✅ 获取到 {len(event_list)} 个工作流事件")
                
                if event_list:
                    print("\n   最近的事件:")
                    for i, event in enumerate(event_list[:3]):
                        event_id = getattr(event, 'id', 'N/A')
                        print(f"   {i+1}. ID: {event_id}")
            else:
                print("✅ 工作流事件 API 可用（当前无事件）")
                
            return True
            
    except Exception as e:
        print(f"❌ 工作流事件 API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workstream_summaries_api():
    """测试工作流摘要 API"""
    print("\n" + "=" * 60)
    print("5. 测试工作流摘要 (Workstream Summaries) API")
    print("=" * 60)
    
    try:
        import pieces_os_client
        from pieces_os_client.api.workstream_summaries_api import WorkstreamSummariesApi
        
        config = pieces_os_client.Configuration(host="http://localhost:39300")
        
        with pieces_os_client.ApiClient(config) as api_client:
            api = WorkstreamSummariesApi(api_client)
            summaries = api.workstream_summaries_snapshot()
            
            if hasattr(summaries, 'iterable') and summaries.iterable:
                summary_list = list(summaries.iterable)
                print(f"✅ 获取到 {len(summary_list)} 个工作流摘要")
                
                if summary_list:
                    print("\n   最近的摘要:")
                    for i, summary in enumerate(summary_list[:3]):
                        summary_id = getattr(summary, 'id', 'N/A')
                        text = getattr(summary, 'summary', {})
                        if hasattr(text, 'text'):
                            text = text.text[:100] + "..." if len(text.text) > 100 else text.text
                        else:
                            text = str(text)[:100]
                        print(f"   {i+1}. ID: {summary_id}")
                        print(f"      内容: {text}")
            else:
                print("✅ 工作流摘要 API 可用（当前无摘要）")
                
            return True
            
    except Exception as e:
        print(f"❌ 工作流摘要 API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vision_events_api():
    """测试视觉事件 API (OCR)"""
    print("\n" + "=" * 60)
    print("6. 测试视觉事件 (Vision Events / OCR) API")
    print("=" * 60)
    
    try:
        import pieces_os_client
        from pieces_os_client.api.workstream_pattern_engine_api import WorkstreamPatternEngineApi
        
        config = pieces_os_client.Configuration(host="http://localhost:39300")
        
        with pieces_os_client.ApiClient(config) as api_client:
            api = WorkstreamPatternEngineApi(api_client)
            
            # 先检查状态
            try:
                status = api.workstream_pattern_engine_processors_vision_status()
                print(f"   视觉处理器状态: {status}")
            except Exception as e:
                print(f"   ⚠️ 无法获取视觉处理器状态: {e}")
            
            # 获取视觉事件
            try:
                events = api.workstream_pattern_engine_processors_vision_events_snapshot()
                
                if hasattr(events, 'iterable') and events.iterable:
                    event_list = list(events.iterable)
                    print(f"✅ 获取到 {len(event_list)} 个视觉事件")
                    
                    if event_list:
                        print("\n   最近的视觉事件:")
                        for i, event in enumerate(event_list[:3]):
                            event_id = getattr(event, 'id', 'N/A')
                            print(f"   {i+1}. ID: {event_id}")
                else:
                    print("✅ 视觉事件 API 可用（当前无事件）")
                    print("   提示: 请确保已启用 Workstream Pattern Engine 并授权屏幕录制权限")
                    
            except Exception as e:
                print(f"⚠️ 视觉事件获取失败: {e}")
                print("   这可能是因为 Workstream Pattern Engine 未启用")
                print("   请在 Pieces Desktop App 中启用并授权屏幕录制权限")
                
            return True
            
    except Exception as e:
        print(f"❌ 视觉事件 API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_activities_api():
    """测试活动 API"""
    print("\n" + "=" * 60)
    print("7. 测试活动 (Activities) API")
    print("=" * 60)
    
    try:
        import pieces_os_client
        from pieces_os_client.api.activities_api import ActivitiesApi
        
        config = pieces_os_client.Configuration(host="http://localhost:39300")
        
        with pieces_os_client.ApiClient(config) as api_client:
            api = ActivitiesApi(api_client)
            activities = api.activities_snapshot()
            
            if hasattr(activities, 'iterable') and activities.iterable:
                activity_list = list(activities.iterable)
                print(f"✅ 获取到 {len(activity_list)} 个活动")
                
                if activity_list:
                    print("\n   最近的活动:")
                    for i, activity in enumerate(activity_list[:3]):
                        activity_id = getattr(activity, 'id', 'N/A')
                        print(f"   {i+1}. ID: {activity_id}")
            else:
                print("✅ 活动 API 可用（当前无活动）")
                
            return True
            
    except Exception as e:
        print(f"❌ 活动 API 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(results: dict):
    """打印测试摘要"""
    print("\n" + "=" * 60)
    print("测试摘要")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {status} - {name}")
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！Pieces OS API 可以正常使用。")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息。")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Pieces OS API 测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    results = {}
    
    # 1. 检查连接
    results["Pieces OS 连接"] = check_pieces_running()
    
    if not results["Pieces OS 连接"]:
        print("\n❌ Pieces OS 未运行，无法继续测试")
        print("   请先安装并启动 Pieces Desktop App")
        print("   下载地址: https://pieces.app/")
        sys.exit(1)
    
    # 2. 健康检查
    results["健康检查 API"] = test_health_api()
    
    # 3. 资源 API
    results["资源 API"] = test_assets_api()
    
    # 4. 工作流事件 API
    results["工作流事件 API"] = test_workstream_events_api()
    
    # 5. 工作流摘要 API
    results["工作流摘要 API"] = test_workstream_summaries_api()
    
    # 6. 视觉事件 API
    results["视觉事件 API"] = test_vision_events_api()
    
    # 7. 活动 API
    results["活动 API"] = test_activities_api()
    
    # 打印摘要
    print_summary(results)


if __name__ == "__main__":
    main()
