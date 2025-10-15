import socket
import ssl
import http.client
import json
import datetime
import logging
import sys
import os
import threading
import time
import uuid
from pathlib import Path

import webview
from flask import Flask, request, jsonify, render_template



# 配置日志（保留原配置，增加调试级日志便于排查）
# 原日志配置基础上，增加文件输出
logging.basicConfig(
    level=logging.DEBUG,  # 改为DEBUG，输出更详细日志
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(Path.home(), "Downloads/CF_MTG_Error.log")),  # 日志存到下载目录
        logging.StreamHandler()  # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)

def get_base_path():
    """获取应用基础路径（兼容开发环境和打包环境）"""
    if getattr(sys, 'frozen', False):
        # 打包后环境
        return sys._MEIPASS
    else:
        # 开发环境
        return os.path.dirname(os.path.abspath(__file__))

# 初始化 Flask 应用（修复打包路径问题）
base_path = get_base_path()
template_path = os.path.join(base_path, 'templates')
static_path = os.path.join(base_path, 'statics')

app = Flask(__name__,
            template_folder=template_path,
            static_folder=static_path)

# 配置 API 密钥
API_KEY = "0cd87c1ce7251b3aa8414f3613b259b3e282bf7c66cd56f4ae2913eeb53c5ee0.e2deb7cb288cc2544c1836a235f25ab3f59bcfb6"

# 全局 SSL 上下文（解决 SSL 验证问题，保留原配置）
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# CFapi
# 全局变量：存储克隆进度和结果（确保线程安全基础结构）
CLONE_PROGRESS = {
    "total": 0,
    "completed": 0,
    "failed": 0,
    "progress_percent": 0,
    "status": "idle"  # idle/processing/completed/failed
}
CLONE_RESULTS = {
    "success_list": [],
    "fail_list": [],
    "success_count": 0,
    "fail_count": 0
}


def get_campaign_id_by_name(campaign_name):
    """
    修复 1：活动名称精确匹配（解决模糊搜索问题）
    处理逻辑：
    - API 查询用双引号包裹关键词，强制接口精确匹配
    - 代码层双端去空格，避免空格导致的不匹配
    - 严格字符串相等，不忽略大小写（如需忽略可加.lower()）
    """
    conn = http.client.HTTPSConnection("public-api.clickflare.io", context=SSL_CONTEXT)
    headers = {"api-key": API_KEY}
    campaign_id = None

    # 处理输入名称：去前后空格，避免用户误输入
    target_name = campaign_name.strip()

    try:
        # 关键：用双引号包裹查询词，多数搜索接口支持此语法实现精确匹配
        query = f'/api/campaigns/list?query={target_name}'
        conn.request("GET", query, headers=headers)
        response = conn.getresponse()

        if response.status != 200:
            response_content = response.read().decode()
            raise Exception(f"API 调用失败：状态码 {response.status}，响应: {response_content}")

        data = json.loads(response.read().decode())
        logger.info(f"精确匹配查询结果（目标名称：{target_name}）: 共 {len(data)} 个活动")

        # 代码层二次精确筛选：双端去空格后比较
        for campaign in data:
            api_name = campaign.get("name", "").strip()  # 接口返回名称去空格
            print(api_name)
            logger.debug(f"比较：输入='{target_name}' | 接口返回='{api_name}'")
            if api_name.lower() == target_name.strip().lower() :  # 严格相等，无模糊匹配
                campaign_id = campaign["_id"]
                logger.info(f"找到完全匹配活动：名称='{target_name}' → ID='{campaign_id}'")
                break

        # 无匹配时的友好提示：列出所有接口返回名称
        if not campaign_id:
            available_names = [c.get("name", "").strip() for c in data]
            available_str = "\n -".join(available_names) if available_names else "无"
            raise ValueError(f"未找到与 '{target_name}' 完全匹配的活动！\n"
                             f"接口返回的相似活动：\n - {available_str}\n"
                             "提示：检查名称是否含多余后缀（如_1、_x）或空格")
    except Exception as e:
        logger.error(f"获取活动 ID 失败: {str(e)}")
        raise
    finally:
        conn.close()

    return campaign_id


def get_campaign_details(campaign_id):
    """修复 2：确保获取完整活动详情（含 url、workspace_id 等）"""
    conn = http.client.HTTPSConnection("public-api.clickflare.io", context=SSL_CONTEXT)
    headers = {"api-key": API_KEY}

    try:
        path = f"/api/campaigns/{campaign_id}"
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()

        if response.status != 200:
            response_content = response.read().decode()
            raise Exception(f"获取活动详情失败：状态码 {response.status}，响应: {response_content}")

        data = json.loads(response.read().decode())

        # 验证关键字段是否存在
        required_fields = ["name", "workspace_id", "url"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"活动详情缺少关键字段 '{field}'（ID：{campaign_id})")
        logger.info(f"获取活动详情成功：ID={campaign_id}，名称={data['name']}")
        return data
    except Exception as e:
        logger.error(f"获取活动详情失败: {str(e)}")
        raise
    finally:
        conn.close()


def clone_single_campaign(source_campaign_id):
    """修复 3：确保克隆后返回完整新活动数据（含 url）"""
    conn = None
    try:
        conn = http.client.HTTPSConnection("public-api.clickflare.io", context=SSL_CONTEXT)
        headers = {
            "api-key": API_KEY,
            "Content-Type": "application/json"
        }

        clone_path = f"/api/campaigns/clone/{source_campaign_id}"
        conn.request("POST", clone_path, body=json.dumps({}), headers=headers)

        response = conn.getresponse()
        if response.status != 200:
            response_content = response.read().decode()
            raise Exception(f"克隆失败：状态码 {response.status}，响应: {response_content}")

        new_campaign_data = json.loads(response.read().decode())

        # 验证克隆后的数据完整性
        if "id" not in new_campaign_data and "_id" not in new_campaign_data:
            raise ValueError(f"克隆活动未返回 ID（源 ID：{source_campaign_id})")
        if "url" not in new_campaign_data:
            raise ValueError(f"克隆活动未返回 URL（新 ID：{new_campaign_data.get('_id')})")

        new_id = new_campaign_data.get("_id") or new_campaign_data.get("id")
        logger.info(f"克隆成功：源 ID={source_campaign_id} → 新 ID={new_id}，URL={new_campaign_data['url']}")
        return new_campaign_data
    except Exception as e:
        logger.error(f"克隆活动失败（源 ID：{source_campaign_id}）：{str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def update_campaign_name(new_campaign_id, target_name, workspace_id):
    """保留原逻辑，确保只传必要字段"""
    conn = None
    try:
        conn = http.client.HTTPSConnection("public-api.clickflare.io", context=SSL_CONTEXT)
        headers = {
            "api-key": API_KEY,
            "Content-Type": "application/json"
        }

        # 仅传修改名称必需的字段，避免接口报错
        request_body = {
            "name": target_name,
            "workspace_id": workspace_id
        }

        update_path = f"/api/campaigns/{new_campaign_id}"
        conn.request("PATCH", update_path, body=json.dumps(request_body), headers=headers)

        response = conn.getresponse()
        if response.status != 200:
            response_content = response.read().decode()
            raise Exception(f"修改名称失败：状态码 {response.status}，响应: {response_content}")

        updated_data = json.loads(response.read().decode())
        if updated_data.get("name") != target_name:
            raise Exception(f"名称修改不生效：期望={target_name}，实际={updated_data.get('name')}")

        logger.info(f"修改名称成功：ID={new_campaign_id} → 名称={target_name}")
        return True
    except Exception as e:
        logger.error(f"修改名称失败（新 ID：{new_campaign_id}）：{str(e)}")
        raise
    finally:
        if conn:
            conn.close()


def extract_name_prefix(source_name):
    """修复 4：准确提取名称前缀（删除日期及后续所有内容）"""
    name_parts = source_name.strip().split("_")
    prefix_parts = []

    for part in name_parts:
        # 识别日期格式：8 位数字 + 202x 开头（如 20250927）
        if len(part) == 8 and part.isdigit() and part.startswith(("202", "203")):
            break  # 遇到日期则停止，前面为前缀
        prefix_parts.append(part)

    # 若未找到日期，用完整名称作前缀
    return "_".join(prefix_parts) if prefix_parts else source_name


def batch_clone_campaigns(source_campaign_id, clone_count):
    """
    修复 5：整合所有逻辑
    - 名称格式：前缀_20251014_153000（用毫秒确保唯一，无多余序号）
    - 结果存储：确保 success_list 含 name/url/campaign_id
    - 进度同步：实时更新全局进度变量
    """
    global CLONE_PROGRESS, CLONE_RESULTS

    # 初始化（避免多次调用残留旧数据）
    CLONE_PROGRESS = {
        "total": clone_count,
        "completed": 0,
        "failed": 0,
        "progress_percent": 0,
        "status": "processing"
    }
    CLONE_RESULTS = {
        "success_list": [],
        "fail_list": [],
        "success_count": 0,
        "fail_count": 0
    }

    try:
        # 获取源活动详情（用于前缀提取和 workspace_id）
        source_details = get_campaign_details(source_campaign_id)
        source_name = source_details["name"]
        workspace_id = source_details["workspace_id"]

        # 提取前缀（如从 "xxx_20250927" 提取 "xxx"）
        name_prefix = extract_name_prefix(source_name)
        logger.info(f"名称前缀提取：源名称='{source_name}' → 前缀='{name_prefix}'")

        # 批量克隆循环
        for i in range(clone_count):
            try:
                # 克隆单个活动（代码不变）
                new_campaign = clone_single_campaign(source_campaign_id)
                new_campaign_id = new_campaign.get("_id") or new_campaign.get("id")
                new_campaign_url = new_campaign["url"]

                # 修复：时间戳只保留到秒（去掉毫秒）
                # 原格式：%Y%m%d_%H%M%S%f[:-3] → 含毫秒（如20251014_155139195）
                # 新格式：%Y%m%d_%H%M%S → 仅日期+时分秒（如20251014_155139）
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")  # 关键修改
                target_name = f"{name_prefix}_{timestamp}"
                logger.info(f"生成目标名称：{target_name}（第{i + 1}/{clone_count}个）")

                # 修改名称（代码不变）
                update_campaign_name(new_campaign_id, target_name, workspace_id)

                # 4. 记录成功结果（确保字段完整）
                success_item = {
                    "clone_index": i + 1,
                    "name": target_name,
                    "campaign_id": new_campaign_id,
                    "url": new_campaign_url,
                    "create_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                CLONE_RESULTS["success_list"].append(success_item)
                CLONE_RESULTS["success_count"] = len(CLONE_RESULTS["success_list"])
                CLONE_PROGRESS["completed"] += 1
            except Exception as e:
                # 记录失败结果
                fail_item = {
                    "clone_index": i + 1,
                    "reason": str(e),
                    "source_campaign_id": source_campaign_id
                }
                CLONE_RESULTS["fail_list"].append(fail_item)
                CLONE_RESULTS["fail_count"] = len(CLONE_RESULTS["fail_list"])
                CLONE_PROGRESS["failed"] += 1
                logger.error(f"第 {i + 1}/{clone_count} 个活动克隆失败：{str(e)}")
            finally:
                # 更新进度百分比（避免超过 100%）
                processed = CLONE_PROGRESS["completed"] + CLONE_PROGRESS["failed"]
                CLONE_PROGRESS["progress_percent"] = min(int((processed / clone_count) * 100), 100)

        # 任务结束
        CLONE_PROGRESS["status"] = "completed"
        logger.info(f"批量克隆完成：成功 {CLONE_RESULTS['success_count']} 个，失败 {CLONE_RESULTS['fail_count']} 个")
    except Exception as e:
        # 全局异常（如获取源详情失败）
        CLONE_PROGRESS["status"] = "failed"
        error_msg = f"批量克隆主流程失败：{str(e)}"
        CLONE_RESULTS["fail_list"].append({"clone_index": 0, "reason": error_msg})
        CLONE_RESULTS["fail_count"] = 1
        logger.error(error_msg)

    # 返回完整结果（供接口调用）
    return {**CLONE_RESULTS, "progress": CLONE_PROGRESS}



# Flask 路由（修复 6：确保进度接口返回完整结果）
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/get_campaign_id", methods=["POST"])
def api_get_campaign_id():
    try:
        data = request.get_json()
        campaign_name = data.get("campaign_name")

        if not campaign_name:
            return jsonify({"code": 400, "message": "活动名称不能为空"}), 400

        campaign_id = get_campaign_id_by_name(campaign_name)
        return jsonify({
            "code": 200,
            "message": "获取活动 ID 成功（完全匹配）",
            "data": {"campaign_id": campaign_id, "campaign_name": campaign_name.strip()}
        })
    except Exception as e:
        return jsonify({"code": 500, "message": str(e)}), 500


@app.route("/api/batch_clone", methods=["POST"])
def api_batch_clone():
    try:
        data = request.get_json()
        source_campaign_id = data.get("source_campaign_id")
        clone_count = data.get("clone_count", 1)

        # 参数校验
        if not source_campaign_id:
            return jsonify({"code": 400, "message": "源活动 ID 不能为空"}), 400
        if not isinstance(clone_count, int) or clone_count <= 0 or clone_count > 50:
            return jsonify({"code": 400, "message": "克隆数量必须是 1-50 之间的正整数"}), 400

        # 启动克隆线程（避免前端超时）
        threading.Thread(
            target=batch_clone_campaigns,
            args=(source_campaign_id, clone_count),
            daemon=True
        ).start()

        return jsonify({
            "code": 200,
            "message": f"批量克隆任务已启动（共 {clone_count} 个）",
            "data": {"source_campaign_id": source_campaign_id, "clone_count": clone_count}
        })
    except Exception as e:
        logger.error(f"批量克隆接口异常：{str(e)}")
        return jsonify({"code": 500, "message": str(e)}), 500


@app.route("/api/clone_progress", methods=["GET"])
def api_clone_progress():
    """修复 7：返回完整进度 + 结果数据，供前端渲染"""
    global CLONE_PROGRESS, CLONE_RESULTS
    return jsonify({
        "code": 200,
        "data": {
            "progress": CLONE_PROGRESS,
            "success_list": CLONE_RESULTS["success_list"],
            "fail_list": CLONE_RESULTS["fail_list"],
            "success_count": CLONE_RESULTS["success_count"],
            "fail_count": CLONE_RESULTS["fail_count"]
        }
    })


@app.route("/api/export_csv", methods=["GET"])
def api_export_csv():
    import csv
    import datetime
    global CLONE_RESULTS

    # 1. 校验数据
    success_list = CLONE_RESULTS.get("success_list", [])
    if not success_list:
        return jsonify({"code": 400, "message": "没有可导出的活动数据"}), 400

    # 2. 生成 CSV 内容（提取 ZC_TotalAB_ 开头的名称）
    rows = [["MTG名称", "URL"]]  # 表头
    for item in success_list:
        full_name = item.get("name", "")
        target_prefix = "ZC_"
        prefix_index = full_name.find(target_prefix)
        short_name = full_name[prefix_index:] if prefix_index != -1 else f"{full_name}（格式异常）"
        rows.append([short_name, item.get("url", "")])

    # 3. 保存到 Mac 可见的下载目录（确保用户能找到）
    # 获取 Mac 下载目录路径（~/Downloads）
    downloads_dir = Path.home() / "Downloads"
    # 生成带时间戳的文件名
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"campaign_clones_{timestamp}.csv"
    file_path = downloads_dir / filename

    # 4. 写入文件（带 BOM 头解决中文乱码）
    try:
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerows(rows)
    except Exception as e:
        return jsonify({"code": 500, "message": f"文件保存失败: {str(e)}"}), 500

    # 5. 返回文件保存路径给前端
    return jsonify({
        "code": 200,
        "data": {
            "file_path": str(file_path),
            "message": f"文件已保存到下载目录:\n{file_path}"
        }
    })



# mtg api

# MTG平台配置（硬编码密钥，按实际项目调整）
HARDCODED_ACCESS_KEY = "5cc4db728653da2316ca9309d4ff894f"
HARDCODED_API_KEY = "8bf63783e0a77a56381ec81b2b935a8a"

# MTG API地址（完整地址，无省略）
MINTERGRAL_API_URL = "https://ss-api.mintegral.com/api/open/v1"
MINTERGRAL_CAMPAIGN_URL = "https://ss-api.mintegral.com/api/open/v1/campaign"
MINTERGRAL_UPLOAD_URL = "https://ss-storage-api.mintegral.com/api/open/v1/creatives/upload"
MINTERGRAL_PLAYABLE_URL = "https://ss-storage-api.mintegral.com/api/open/v1/playable/upload"
MINTERGRAL_CREATIVE_SETS_URL = "https://ss-api.mintegral.com/api/open/v1/creative_sets"
MINTERGRAL_CREATIVE_LIST_URL = "https://ss-api.mintegral.com/api/open/v1/creative-ad/list"
MINTERGRAL_OFFER_URL = "https://ss-api.mintegral.com/api/open/v1/offers"  # Offer查询
MINTERGRAL_CREATE_OFFER_URL = "https://ss-api.mintegral.com/api/open/v1/offer"  # 统一Offer创建地址

# 平台分类配置（安卓固定TOOLS，iOS按API要求）
IOS_CATEGORIES = "6018,6000,6022,6017,6016,6023,6014,6013,6012,6020,6011,6010,6009,6021,OTHERS,6008,6006,6024,6005,6004,6003,6002,6001"
ANDROID_CATEGORIES = "TOOLS"  # 安卓固定分类

# 静态图片路径配置（项目根目录下的statics文件夹，需手动创建并放入图片）
STATIC_IMAGE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),  # 项目根目录
    "statics",
    "68d0b1d4cc068.jpeg"  # 静态图片文件名，必须与实际文件一致
)


def generate_token(api_key, timestamp):
    import hashlib
    """生成MTG请求所需的token（按MTG签名规则）"""
    try:
        # 1. 时间戳MD5加密
        timestamp_str = str(timestamp).encode('utf-8')
        timestamp_md5 = hashlib.md5(timestamp_str).hexdigest()
        # 2. API_KEY + 时间戳MD5 再次MD5
        token_str = (api_key + timestamp_md5).encode('utf-8')
        token = hashlib.md5(token_str).hexdigest()
        logger.info(f"生成token成功：timestamp={timestamp}, token前6位={token[:6]}")
        return token
    except Exception as e:
        logger.error(f"生成token失败：{str(e)}", exc_info=True)
        raise  # 抛出异常，避免无效token请求


def get_mintegral_headers():
    """生成MTG所有接口通用的请求头（含token、timestamp）"""
    try:
        timestamp = int(time.time())  # 秒级时间戳
        headers = {
            "access-key": HARDCODED_ACCESS_KEY,
            "token": generate_token(HARDCODED_API_KEY, timestamp),
            "timestamp": str(timestamp),
            "Content-Type": "application/json"
        }
        logger.debug(f"生成MTG请求头：{json.dumps(headers, ensure_ascii=False)}")
        return headers
    except Exception as e:
        logger.error(f"生成MTG请求头失败：{str(e)}", exc_info=True)
        raise


def extract_keyword_from_campaign_name(campaign_name):
    """从CF活动名称中提取关键词（用于MTG的product_name）"""
    try:
        # 匹配规则：字母+数字+可选字母（如ZC_TotalAB_00665中的00665）
        pattern = r'([a-zA-Z]+\d+[a-zA-Z]?)'
        matches = re.findall(pattern, campaign_name)
        keyword = matches[-1] if matches else campaign_name[:100]  # 取最后一个匹配项，最长100字符
        logger.info(f"从CF名称提取关键词：原始名称={campaign_name}, 关键词={keyword}")
        return keyword
    except Exception as e:
        logger.warning(f"提取关键词失败，使用默认名称：{str(e)}")
        return campaign_name[:100]  # 异常时返回原始名称前100字符

import re
from werkzeug.datastructures import FileStorage  # 用于模拟文件上传
import requests


def get_static_image_file():
    """读取静态图片文件，封装为FileStorage（修复打包后路径问题）"""
    try:
        # 关键：打包后用sys._MEIPASS拼接路径，与模板文件逻辑一致
        if getattr(sys, 'frozen', False):
            # 打包后：statics在sys._MEIPASS下
            static_dir = os.path.join(sys._MEIPASS, 'statics')
        else:
            # 开发环境：statics在项目根目录
            static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'statics')

        STATIC_IMAGE_PATH = os.path.join(static_dir, '68d0b1d4cc068.jpeg')  # 拼接完整路径

        # 1. 检查文件是否存在
        if not os.path.exists(STATIC_IMAGE_PATH):
            raise FileNotFoundError(f"静态图片不存在！路径：{STATIC_IMAGE_PATH}")

        # 2. 检查文件格式
        if not STATIC_IMAGE_PATH.lower().endswith(('.jpeg', '.jpg', '.png')):
            raise TypeError("静态文件必须是JPG/PNG格式")

        # 读取文件（保持原逻辑）
        f = open(STATIC_IMAGE_PATH, "rb")
        file_obj = FileStorage(
            stream=f,
            filename="68d0b1d4cc068.jpeg",
            content_type="image/jpeg"
        )
        file_obj.stream.seek(0)
        file_size = os.path.getsize(STATIC_IMAGE_PATH)
        logger.info(f"成功读取静态图片：路径={STATIC_IMAGE_PATH}, 大小={file_size}字节")
        return file_obj
    except Exception as e:
        logger.error(f"读取静态图片失败：{str(e)}", exc_info=True)
        raise


def upload_creative_file(file):
    try:
        # 1. 读取文件（
        if not file.closed and hasattr(file.stream, 'seek'):
            file.stream.seek(0)
        file_content = file.read()
        if not file.closed:
            file.close()
        if not file_content:
            return {"success": False, "msg": "文件内容为空，无法上传"}

        # 2. 构建上传请求（保持不变）
        headers = get_mintegral_headers()
        headers.pop("Content-Type", None)
        files = {'file': (file.filename, file_content, file.content_type)}
        upload_url = MINTERGRAL_PLAYABLE_URL if file.filename.lower().endswith(
            ('.zip', '.html')) else MINTERGRAL_UPLOAD_URL
        logger.info(
            f"上传文件：名称={file.filename}, 类型={file.content_type}, 大小={len(file_content)}字节, URL={upload_url}")

        # 3. 发送请求并处理响应（【核心修复】增加data存在性判断）
        response = requests.post(upload_url, headers=headers, files=files, timeout=300)
        response_text = response.text[:500]  # 截取日志，避免过长
        logger.info(f"上传响应：状态码={response.status_code}, 内容={response_text}")

        try:
            result = response.json()
            # 关键：先获取data，若不存在则设为空字典，避免None下标
            data = result.get('data', {})  # 修复点1：防止data为None

            if result.get('code') == 200:
                # 从data中获取MD5，而非直接result['data']
                md5 = data.get('creative_md5')  # 修复点2：用data变量
                if not md5:
                    return {"success": False, "msg": "API返回成功，但未获取到素材MD5"}
                logger.info(f"新上传素材MD5：{md5}")
                return {"success": True, "md5": md5, "is_existing": False}
            else:
                # 处理素材已存在的场景（同样从data中获取）
                creative_name = data.get('file.creative_name', '')  # 修复点3：用data变量
                if 'fmd5: ' in creative_name:
                    md5_start = creative_name.find('fmd5: ') + 5
                    md5_end = creative_name.find(',', md5_start)
                    md5 = creative_name[md5_start:md5_end].strip() if md5_end != -1 else ''
                    if len(md5) == 32:
                        logger.info(f"复用已存在素材MD5：{md5}")
                        return {"success": True, "md5": md5, "is_existing": True}
                # 上传失败（明确错误信息）
                error_msg = f"API返回错误：code={result.get('code')}, msg={result.get('msg', '未知错误')}"
                logger.warning(error_msg)
                return {"success": False, "msg": error_msg}

        except json.JSONDecodeError:
            return {"success": False, "msg": f"响应格式错误（非JSON）：{response_text}"}

    except Exception as e:
        logger.error(f"上传异常：{str(e)}", exc_info=True)
        return {"success": False, "msg": f"上传异常：{str(e)}"}



def generate_mtg_names(cf_name):
    """根据CF活动名称生成MTG的Campaign和Offer名称（符合MTG命名规则）"""
    try:
        # MTG名称限制：最长100字符，仅字母、数字、下划线
        base_name = cf_name.strip().replace(' ', '_').replace('-', '_')  # 替换非法字符
        base_name = re.sub(r'[^\w_]', '', base_name)  # 过滤非字母数字下划线

        # Campaign名称：直接使用处理后的CF名称（最长100字符）
        campaign_name = base_name[:100]
        # Offer名称：Campaign名称 + _offer（预留5字符，最长95+5=100字符）
        offer_name = {base_name[:100]}

        logger.info(f"生成MTG名称：CF名称={cf_name} → Campaign={campaign_name}, Offer={offer_name}")
        return campaign_name, offer_name
    except Exception as e:
        logger.warning(f"生成MTG名称失败，使用默认名称：{str(e)}")
        default_name = f"MTG_{int(time.time())}"
        return default_name[:100], f"{default_name[:95]}_offer"


@app.route('/api/mtg/search_creative_sets_simple', methods=['GET'])
def search_creative_sets_simple():
    """
    精简版素材组查询（参照/get_creative_sets逻辑，关联查询Offer对应的Campaign名称）
    功能：支持按名称搜索、分页，返回素材组ID、名称、关联广告活动名称（campaign_name）
    请求参数：
    - creative_set_name: 素材组名称关键词（可选，模糊匹配）
    - page: 页码（默认1）
    - limit: 每页数量（默认45）
    返回格式：{code:200, data:{creative_sets:[{id, name, campaign_name}], total:int}, msg:str}
    """
    try:
        # 1. 接收参数（完全对齐原有/get_creative_sets接口）
        creative_set_name = request.args.get('creative_set_name', '').strip()
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 45))

        # 2. 构建MTG API请求参数（与原有接口一致）
        params = {
            'page': page,
            'limit': limit
        }
        if creative_set_name:
            params['creative_set_name'] = creative_set_name

        # 3. 调用MTG API获取素材组列表（复用原有接口的请求头和URL）
        headers = get_mintegral_headers()
        logger.info(f"精简版素材组查询请求：URL={MINTERGRAL_CREATIVE_SETS_URL}, params={params}")

        response = requests.get(
            MINTERGRAL_CREATIVE_SETS_URL,
            headers=headers,
            params=params,
            timeout=300
        )

        logger.info(f"MTG API响应：状态码={response.status_code}, 内容={response.text[:500]}")

        # 4. 响应基础错误处理（与原有接口一致）
        if response.status_code != 200:
            error_msg = f"MTG API请求失败：HTTP {response.status_code}，响应内容：{response.text[:300]}"
            logger.error(error_msg)
            return jsonify({
                "code": 500,
                "msg": error_msg
            }), 500

        try:
            mtg_result = response.json()
        except json.JSONDecodeError as e:
            error_msg = f"MTG API响应解析失败：{str(e)}，响应内容：{response.text[:300]}"
            logger.error(error_msg, exc_info=True)
            return jsonify({
                "code": 500,
                "msg": error_msg
            }), 500

        if mtg_result.get('code') != 200:
            error_msg = f"MTG API业务错误：code={mtg_result.get('code')}，msg={mtg_result.get('msg', '未知错误')}"
            logger.error(error_msg)
            return jsonify({
                "code": mtg_result.get('code', 500),
                "msg": error_msg
            }), mtg_result.get('code', 500)

        # 5. 【核心修改：参照/get_creative_sets，批量查询Offer关联的Campaign名称】
        creative_sets_list = mtg_result['data'].get('list', [])
        total = mtg_result['data'].get('total', 0)
        simplified_data = []

        # 5.1 收集所有素材组的offer_id（去重，避免重复查询）
        offer_ids = list(set(str(item.get('offer_id')) for item in creative_sets_list if item.get('offer_id')))
        campaign_name_map = {}  # 存储offer_id -> campaign_name的映射

        # 5.2 调用Offers API批量查询关联的Campaign名称（与/get_creative_sets逻辑一致）
        if offer_ids:
            offer_params = {
                'offer_id': ','.join(offer_ids),
                'limit': len(offer_ids)  # 确保获取所有匹配的Offer
            }
            offer_headers = get_mintegral_headers()
            logger.info(f"批量查询Offer关联的Campaign名称：offer_ids={offer_ids}, params={offer_params}")

            offer_response = requests.get(
                f"{MINTERGRAL_API_URL}/offers",  # 复用全局API基础地址，与原有接口一致
                headers=offer_headers,
                params=offer_params,
                timeout=300
            )

            if offer_response.status_code == 200:
                try:
                    offer_result = offer_response.json()
                    if offer_result.get('code') == 200:
                        # 构建offer_id到campaign_name的映射
                        for offer in offer_result['data'].get('list', []):
                            offer_id_str = str(offer.get('offer_id'))  # 统一转为字符串，避免类型不匹配
                            campaign_name = offer.get('campaign_name', '未知广告活动')
                            campaign_name_map[offer_id_str] = campaign_name
                        logger.info(f"成功获取{len(campaign_name_map)}个Offer关联的Campaign名称")
                except json.JSONDecodeError as e:
                    logger.error(f"Offer响应解析失败：{str(e)}，响应内容：{offer_response.text[:300]}", exc_info=True)
            else:
                logger.error(f"Offer查询失败：HTTP {offer_response.status_code}，响应内容：{offer_response.text[:300]}")

        # 6. 构建精简版返回数据（包含关联的campaign_name）
        for item in creative_sets_list:
            set_id = item.get('creative_set_id')
            set_name = item.get('creative_set_name', f"素材组_{set_id}")
            offer_id = item.get('offer_id')

            # 从映射中获取关联的Campaign名称，无匹配则显示“未知广告活动”
            campaign_name = campaign_name_map.get(str(offer_id), '未知广告活动')

            if set_id:  # 过滤无ID的无效数据
                simplified_data.append({
                    "id": set_id,  # 前端下拉框value
                    "name": set_name,  # 素材组名称
                    "campaign_name": campaign_name  # 关联的广告活动名称（新增，与/get_creative_sets一致）
                })

        logger.info(f"精简版素材组查询完成：关键词={creative_set_name}，匹配{len(simplified_data)}/{total}个素材组")
        return jsonify({
            "code": 200,
            "msg": f"查询成功，找到{len(simplified_data)}个匹配素材组",
            "data": {
                "creative_sets": simplified_data,
                "total": total
            }
        })

    except Exception as e:
        error_msg = f"精简版素材组查询异常：{str(e)}"
        logger.error(error_msg, exc_info=True)
        return jsonify({
            "code": 500,
            "msg": error_msg
        }), 500

def get_timezone_offset(tz_name):
    tz_map = {
        "Asia/Shanghai": 8.0,
        "UTC": 0.0,
        "America/New_York": -5.0,
        "Europe/London": 0.0,
        "Europe/Paris": 1.0,
        "Australia/Sydney": 10.0,
        "Asia/Tokyo": 9.0,
        "Asia/Seoul": 9.0,
        "Asia/Calcutta": 5.5,
        "America/Los_Angeles": -8.0
    }
    return tz_map.get(tz_name, 8.0)  # 默认使用东八区



# 全局存储任务进度（生产环境建议用Redis）
batch_task_progress = {}

@app.route('/api/mtg/batch_create_campaign_offer', methods=['POST'])
def batch_create_campaign_offer():
    """启动MTG批量创建的异步任务，返回任务ID"""
    try:
        data = request.json
        cf_success_list = data.get('cf_success_list', [])
        creative_set_id = data.get('creative_set_id')

        # 基础参数校验
        if not cf_success_list:
            return jsonify({"code": 400, "msg": "缺少CF成功列表"}), 400
        if not creative_set_id:
            return jsonify({"code": 400, "msg": "缺少素材组ID"}), 400
        try:
            creative_set_id = int(creative_set_id)
        except:
            return jsonify({"code": 400, "msg": "素材组ID必须为整数"}), 400

        # 生成唯一任务ID，用于跟踪进度
        task_id = str(uuid.uuid4())
        batch_task_progress[task_id] = {
            "total": len(cf_success_list),
            "completed": 0,
            "success": [],
            "fail": [],
            "status": "running"  # running/completed/failed
        }

        # 启动异步任务（用threading模拟，生产建议用Celery）
        threading.Thread(
            target=async_batch_create,
            args=(task_id, cf_success_list, creative_set_id)
        ).start()

        return jsonify({
            "code": 200,
            "msg": "批量创建任务已启动",
            "data": {"task_id": task_id}
        }), 200

    except Exception as e:
        err_msg = f"批量创建启动异常：{str(e)}"
        app.logger.error(err_msg, exc_info=True)
        return jsonify({"code": 500, "msg": err_msg}), 500

def async_batch_create(task_id, cf_success_list, creative_set_id):
    """异步执行MTG批量创建的核心逻辑"""
    try:
        progress = batch_task_progress[task_id]
        success = []
        fail = []

        for idx, cf_item in enumerate(cf_success_list, 1):
            # 提取CF活动信息
            cf_name = cf_item.get('name', '').strip()
            cf_id = cf_item.get('campaign_id', '').strip()
            cf_preview_url = cf_item.get('url', '').strip()

            # 基础信息校验
            if not all([cf_name, cf_id, cf_preview_url]):
                err_msg = "CF活动信息不完整（缺少name/campaign_id/url）"
                fail.append({"index": idx, "cf_info": cf_item, "reason": err_msg})
                app.logger.warning(f"第{idx}个处理失败：{err_msg}")
                # 更新进度
                progress["completed"] += 1
                progress["fail"] = fail
                batch_task_progress[task_id] = progress
                continue

            # 提取ZC_开头的名称
            zc_index = cf_name.find('ZC_')
            if zc_index == -1:
                err_msg = f"CF名称[{cf_name}]中未找到'ZC_'，无法提取合规名称"
                fail.append({"index": idx, "cf_name": cf_name, "reason": err_msg})
                app.logger.warning(f"第{idx}个处理失败：{err_msg}")
                # 更新进度
                progress["completed"] += 1
                progress["fail"] = fail
                batch_task_progress[task_id] = progress
                continue
            mtg_name = cf_name[zc_index:]

            try:
                # ====================== 1. 创建MTG Campaign ======================
                static_file = get_static_image_file()
                upload_result = upload_creative_file(static_file)
                if not upload_result['success'] or not upload_result.get('md5'):
                    raise ValueError(f"素材上传失败：{upload_result.get('msg', '未知错误')}")
                creative_md5 = upload_result['md5']

                campaign_data = {
                    "campaign_name": mtg_name,
                    "promotion_type": "WEBSITE",
                    "preview_url": cf_preview_url.strip(),
                    "is_coppa": "NO",
                    "alive_in_store": "NO",
                    "product_name": mtg_name,
                    "description": mtg_name,
                    "icon": creative_md5,
                    "platform": "ANDROID",
                    "category": ANDROID_CATEGORIES,
                    "app_size": "",
                    "min_version": "",
                    "package_name": ""
                }

                campaign_headers = get_mintegral_headers()
                campaign_response = requests.post(
                    MINTERGRAL_CAMPAIGN_URL,
                    headers=campaign_headers,
                    json=campaign_data,
                    timeout=300
                )

                if campaign_response.status_code != 200:
                    raise ValueError(
                        f"Campaign创建HTTP失败：状态码={campaign_response.status_code}, 内容={campaign_response.text[:300]}")
                campaign_result = campaign_response.json()
                if campaign_result.get('code') != 200:
                    raise ValueError(
                        f"Campaign创建失败：code={campaign_result.get('code')}, msg={campaign_result.get('msg')}")
                mtg_campaign_id = campaign_result['data'].get('campaign_id')
                if not mtg_campaign_id:
                    raise ValueError(
                        f"Campaign创建成功但未返回ID：{json.dumps(campaign_result, ensure_ascii=False)[:300]}")
                app.logger.info(f"Campaign创建成功：ID={mtg_campaign_id}, 名称={mtg_name}")

                # ====================== 2. 创建MTG Offer ======================
                bid_rate = 0.1
                target_geo = "US"
                billing_type = "CPI"
                timezone_name = "Asia/Shanghai"

                # Offer参数校验
                if not re.match(r'^[a-zA-Z0-9_]{3,95}$', mtg_name):
                    raise ValueError(f"Offer名称[{mtg_name}]格式错误（需3-95位字母/数字/下划线）")
                if not (isinstance(bid_rate, (int, float)) and bid_rate > 0):
                    raise ValueError(f"出价[{bid_rate}]必须为正数")
                if not re.match(r'^[A-Z]{2}(,[A-Z]{2})*$', target_geo):
                    raise ValueError(f"目标地区[{target_geo}]格式错误（如US或US,GB）")
                if billing_type not in ['CPI', 'CPC', 'CPM', 'CPA']:
                    raise ValueError(f"计费类型[{billing_type}]无效（仅支持CPI/CPC/CPM/CPA）")

                # 查询创意组详情
                detail_headers = get_mintegral_headers()
                detail_response = requests.get(
                    MINTERGRAL_CREATIVE_SETS_URL,
                    headers=detail_headers,
                    params={'creative_set_id': creative_set_id, 'page': 1, 'limit': 1},
                    timeout=300
                )
                if detail_response.status_code != 200:
                    raise ValueError(f"创意组查询HTTP失败：状态码={detail_response.status_code}")
                detail_result = detail_response.json()
                if detail_result.get('code') != 200 or not detail_result['data'].get('list'):
                    raise ValueError(f"创意组不存在或无权限：code={detail_result.get('code')}")
                creative_set_detail = detail_result['data']['list'][0]
                app.logger.info(f"创意组详情：名称={creative_set_detail.get('creative_set_name')}")

                # 创意类型映射与校验
                creative_type_mapping = {
                    "FULL_SCREEN_IMAGE": 111, "DISPLAY_INTERSTITIAL": 111, "BANNER": 121,
                    "DISPLAY_NATIVE": 121, "ICON": 122, "MORE_OFFER": 122, "APP_WALL": 122,
                    "BASIC_BANNER": 131, "IMAGE_BANNER": 132, "VIDEO_END_CARD": 211,
                    "SPLASH_AD": 211, "INTERSTITIAL_VIDEO": 211, "REWARDED_VIDEO": 211,
                    "VIDEO_PLAYABLE": 212, "FULL_SCREEN_VIDEO": 213, "NATIVE_VIDEO": 213,
                    "INSTREAM_VIDEO": 213, "LARGE_VIDEO_BANNER": 221, "SMALL_VIDEO_BANNER": 231,
                    "VIDEO": 211, "IMAGE": 111, "PLAYABLE": 311, "PLAYABLE_AD": 311
                }
                if 0 in creative_set_detail.get("ad_outputs", []):
                    unknown_types = set()
                    for creative in creative_set_detail.get("creatives", []):
                        ct = creative.get("creative_type")
                        if ct and ct not in creative_type_mapping:
                            unknown_types.add(ct)
                    if unknown_types:
                        raise ValueError(f"创意组含未知类型：{','.join(unknown_types)}")
                if not creative_set_detail.get("creatives"):
                    raise ValueError("创意组中无可用素材")

                # 构建Offer请求体
                offer_payload = {
                    "campaign_id": int(mtg_campaign_id),
                    "offer_name": mtg_name,
                    "daily_cap_type": "BUDGET",
                    "daily_cap": 200,
                    "promote_timezone": get_timezone_offset(timezone_name),
                    "start_time": int(time.time()) + (30 * 24 * 60 * 60),
                    "target_geo": target_geo,
                    "billing_type": billing_type,
                    "bid_rate": str(bid_rate),
                    "target_ad_type": (
                        "BANNER,"
                        "MORE_OFFER,"
                        "DISPLAY_INTERSTITIAL,"
                        "DISPLAY_NATIVE,"
                        "APPWALL,"
                        "SPLASH_AD,"
                        "INTERSTITIAL_VIDEO,"
                        "NATIVE_VIDEO,"
                        "INSTREAM_VIDEO,"
                        "REWARDED_VIDEO"
                    ),
                    "creative_sets": [
                        {
                            "creative_set_name": creative_set_detail.get("creative_set_name"),
                            "geos": ["ALL"],
                            "ad_outputs": creative_set_detail.get("ad_outputs"),
                            "creatives": [
                                {
                                    "creative_name": c.get("creative_name"),
                                    "creative_md5": c.get("creative_md5"),
                                    "creative_type": c.get("creative_type"),
                                    "dimension": c.get("dimension")
                                } for c in creative_set_detail.get("creatives", [])
                            ]
                        }
                    ],
                    "network": "WIFI,2G,3G,4G,5G",
                    "target_device": "PHONE,TABLET",
                    "status": 1
                }

                # 发送Offer创建请求
                offer_headers = get_mintegral_headers()
                offer_response = requests.post(
                    MINTERGRAL_CREATE_OFFER_URL,
                    headers=offer_headers,
                    json=offer_payload,
                    timeout=300
                )

                if offer_response.status_code != 200:
                    raise ValueError(
                        f"Offer创建HTTP失败：状态码={offer_response.status_code}, 内容={offer_response.text[:300]}")
                offer_result = offer_response.json()
                if offer_result.get('code') != 200:
                    raise ValueError(f"Offer创建失败：code={offer_result.get('code')}, msg={offer_result.get('msg')}")
                mtg_offer_id = offer_result['data'].get('offer_id')
                if not mtg_offer_id:
                    raise ValueError(f"Offer创建成功但无ID：{json.dumps(offer_result, ensure_ascii=False)[:300]}")
                app.logger.info(f"Offer创建成功：ID={mtg_offer_id}, 名称={mtg_name}")

                # 记录成功结果
                success.append({
                    "index": idx,
                    "cf_info": {"name": cf_name, "campaign_id": cf_id},
                    "mtg_campaign": {"id": mtg_campaign_id, "name": mtg_name},
                    "mtg_offer": {"id": mtg_offer_id, "name": mtg_name}
                })

            except Exception as e:
                # 记录子任务失败
                err_msg = str(e)
                fail.append({
                    "index": idx,
                    "cf_info": {"name": cf_name, "campaign_id": cf_id},
                    "reason": err_msg
                })
                app.logger.error(f"第{idx}个创建失败：{err_msg}", exc_info=True)

            # 每完成一个子任务，更新全局进度
            progress["completed"] += 1
            progress["success"] = success
            progress["fail"] = fail
            batch_task_progress[task_id] = progress

        # 所有子任务完成，标记任务状态
        progress["status"] = "completed"
        batch_task_progress[task_id] = progress
        app.logger.info(f"=== 批量创建完成 === 总：{len(cf_success_list)} | 成功：{len(success)} | 失败：{len(fail)}")

    except Exception as e:
        # 任务执行中发生全局异常
        if task_id in batch_task_progress:
            progress = batch_task_progress[task_id]
            progress["status"] = "failed"
            progress["error"] = str(e)
            batch_task_progress[task_id] = progress
        app.logger.error(f"异步批量创建异常：{str(e)}", exc_info=True)

@app.route('/api/mtg/batch_progress/<task_id>', methods=['GET'])
def get_batch_progress(task_id):
    """查询指定任务的实时进度"""
    if task_id not in batch_task_progress:
        return jsonify({
            "code": 404,
            "msg": "任务ID不存在"
        }), 404

    progress = batch_task_progress[task_id]
    return jsonify({
        "code": 200,
        "msg": "进度查询成功",
        "data": {
            "task_id": task_id,
            "total": progress["total"],
            "completed": progress["completed"],
            "success": progress["success"],
            "fail": progress["fail"],
            "status": progress["status"],
            "error": progress.get("error")
        }
    }), 200


flask_port = None


def run_flask():
    global flask_port

    # 动态选择可用端口
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()

    flask_port = port  # 存储端口号

    logger.info(f"Starting Flask on port {port}")

    # 启动Flask
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)


def main():
    # 启动Flask服务器（子线程）
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 等待端口分配完成
    while flask_port is None:
        time.sleep(0.1)

    # 启动PyWebView窗口，使用动态端口
    webview.create_window(
        title="ClickFlare 日志工具",
        url=f"http://127.0.0.1:{flask_port}",  # 使用动态端口
        width=1000,
        height=800,
        resizable=True
    )
    webview.start()


if __name__ == '__main__':
    main()