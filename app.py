from flask import Flask, render_template, request, jsonify, session
from zhipuai import ZhipuAI
import re
from enum import Enum
import logging
from datetime import datetime

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = '46b99b6ba01d4b38a1f06045897d37d3.YAvTpKxoYsI3T9y5'

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 智谱AI配置
GLM_API_KEY = "46b99b6ba01d4b38a1f06045897d37d3.YAvTpKxoYsI3T9y5"
client = ZhipuAI(api_key=GLM_API_KEY)

# 用户类型枚举
class UserType(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    TEACHER = "teacher"

# 服务层：AI服务
class AIService:
    @staticmethod
    def get_system_prompt(user_type):
        """根据用户类型生成系统提示"""
        prompts = {
            UserType.BEGINNER: (
                "你是一个耐心细致的编程教育助手，面向编程初学者。"
                "请用简单易懂的语言解释概念，避免专业术语。"
                "回答要分步骤进行，每一步都要清晰明确。"
                "提供实际例子帮助理解。"
                "格式要求：\n1. 第一步\n2. 第二步\n...\n示例：<简单代码示例>"
            ),
            UserType.INTERMEDIATE: (
                "你是一个专业的编程助手，面向有一定基础的开发者。"
                "回答要详细且结构化，包含必要的技术细节。"
                "提供优化建议和最佳实践。"
                "适当使用专业术语但需解释。"
                "格式要求：\n### 问题分析\n### 解决方案\n### 优化建议"
            ),
            UserType.ADVANCED: (
                "你是一个高级技术专家，面向资深开发者。"
                "回答要深入且精准，可以直接使用专业术语。"
                "关注性能优化、系统设计和底层原理。"
                "提供多种解决方案并分析优缺点。"
                "格式要求：\n## 方案一\n优点：\n缺点：\n## 方案二..."
            ),
            UserType.TEACHER: (
                "你是一个教学专家，面向编程教育工作者。"
                "提供适合教学的解释方式。"
                "包含教学目标、关键概念和常见误区。"
                "建议教学活动和评估方法。"
                "格式要求：\n### 教学目标\n### 关键概念\n### 常见误区\n### 教学活动建议"
            )
        }
        return prompts.get(user_type, prompts[UserType.BEGINNER])

    @staticmethod
    def generate_response(user_input, user_type, chat_history=None):
        """生成AI回复"""
        try:
            messages = [
                {"role": "system", "content": AIService.get_system_prompt(user_type)},
                *([{"role": h["role"], "content": h["content"]} for h in chat_history] if chat_history else []),
                {"role": "user", "content": user_input}
            ]
            
            response = client.chat.completions.create(
                model="glm-4",
                messages=messages,
                temperature=0.7
            )
            
            return Utils.remove_html_tags(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"生成AI回复失败: {str(e)}")
            raise

# 工具类
class Utils:
    @staticmethod
    def remove_html_tags(text):
        """清理HTML标签"""
        return re.sub('<.*?>', '', text)
    
    @staticmethod
    def validate_user_type(user_type):
        """验证用户类型是否有效"""
        return user_type in [t.value for t in UserType]

# 控制器层
@app.route('/')
def index():
    """首页路由"""
    if 'chat_history' not in session:
        session['chat_history'] = []
    if 'user_type' not in session:
        session['user_type'] = UserType.BEGINNER.value
    if 'conversations' not in session:
        session['conversations'] = []
    return render_template('chat.html')

@app.route('/set_user_type', methods=['POST'])
def set_user_type():
    """设置用户类型"""
    try:
        user_type = request.json.get('user_type')
        if not Utils.validate_user_type(user_type):
            return jsonify({"error": "无效的用户类型"}), 400
            
        session['user_type'] = user_type
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"设置用户类型失败: {str(e)}")
        return jsonify({"error": "服务器错误"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        user_input = request.json.get('question', '').strip()
        if not user_input:
            return jsonify({"error": "输入不能为空"}), 400

        # 获取用户类型，默认为初学者
        user_type = UserType(session.get('user_type', UserType.BEGINNER.value))
        
        # 将用户输入加入历史
        if 'chat_history' not in session:
            session['chat_history'] = []
        
        session['chat_history'].append({"role": "user", "content": user_input})
        
        # 获取AI回复
        ai_reply = AIService.generate_response(
            user_input, 
            user_type,
            session['chat_history']
        )
        
        # 保存AI回复
        session['chat_history'].append({"role": "assistant", "content": ai_reply})
        
        # 生成对话标题（取前30个字符）
        if len(session['chat_history']) == 2:  # 新对话
            conversation_title = user_input[:30] + ("..." if len(user_input) > 30 else "")
            if 'conversations' not in session:
                session['conversations'] = []
            session['conversations'].append({
                'title': conversation_title,
                'history': session['chat_history'].copy(),
                'timestamp': datetime.now().isoformat()
            })
        
        session.modified = True
        
        return jsonify({
            "reply": ai_reply,
            "conversation_id": len(session.get('conversations', [])) - 1
        })

    except Exception as e:
        logger.error(f"处理聊天请求失败: {str(e)}")
        return jsonify({"error": "处理请求时出错"}), 500

@app.route('/get_conversations', methods=['GET'])
def get_conversations():
    """获取对话历史列表"""
    try:
        conversations = session.get('conversations', [])
        return jsonify({
            "conversations": conversations,
            "status": "success"
        })
    except Exception as e:
        logger.error(f"获取对话历史失败: {str(e)}")
        return jsonify({"error": "获取对话历史失败"}), 500

@app.route('/get_conversation/<int:conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """获取特定对话"""
    try:
        conversations = session.get('conversations', [])
        if conversation_id < 0 or conversation_id >= len(conversations):
            return jsonify({"error": "无效的对话ID"}), 400
            
        return jsonify({
            "conversation": conversations[conversation_id],
            "status": "success"
        })
    except Exception as e:
        logger.error(f"获取对话失败: {str(e)}")
        return jsonify({"error": "获取对话失败"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)