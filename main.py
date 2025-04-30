from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from vanna.flask import VannaFlaskApp
from qianfan import Qianfan
from openai import OpenAI
import json
import pymysql
from MyCache import SemanticCache
import data_clean
import connect_Vanna
import add_cache

app = Flask(__name__)

# 初始化语义缓存
semantic_cache = SemanticCache()

# client = Qianfan(
#     access_key="ALTAKDNn6IRh82PyYPBxFb1T6m",
#     secret_key="28ffc2fc7a9f4097891b0fa324b064b4",
# )

# 调用阿里云大模型的API
client = OpenAI(
    api_key='sk-3ef85faf997b4bc586855975a20b4823',
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 调用Vanna中的智能体并连接本地数据库
MyVanna = connect_Vanna.db_connect(
    model_name='general_staff',
    api_key='4452c6d4d6764f75b71c27df3a221371',
    host='kphone01o.mysql.rds.aliyuncs.com',
    user='aitemp_admin',
    password='aitemp-admin123',
    port=3306,
    dbname='ks_circle_system'
)


# 在前端渲染主页面
@app.route('/')
def index():
    return render_template('index.html')


# 主功能(调用Vanna大模型生成sql，调用deepseek大模型生成echarts和数据分析报告)
@app.route('/ask', methods=['GET'])
def ask_question():
    question = request.args.get('question')  # 获取前端用户输入的问题
    if not question:
        return jsonify({'error': '问题不能为空'}), 400  # 如果问题非空则报错

    def generate():  # 先尝试在缓存中匹配问题，如果缓存中有则直接调用缓存的sql和echarts，减少调用API的次数从而降低成本
        try:
            cached = semantic_cache.get(question)  # 在缓存中匹配问题
            if cached:
                sql, echarts_code = cached
                yield f"event: sql\ndata: {json.dumps({'sql': sql})}\n\n"

                data = MyVanna.run_sql(sql)
                yield f"event: table\ndata: {data.to_json(orient='records')}\n\n"

                yield f"event: echarts\ndata: {json.dumps(echarts_code)}\n\n"

                # 生成流式分析报告
                analysis_prompt = f"""
                我们是无锡新格尔门窗有限公司，一家专注于门窗研发、生产与销售的企业，主要服务于建筑装饰和家居装修市场。
                你是一个资深商业数据分析师，擅长从数据中提炼业务洞察。请根据以下问题、数据和图表，结合我们公司的情况生成一份结构化的商业分析报告：

                **输入数据**:
                问题: {question}
                数据: {data}
                图表配置: {echarts_code}

                **生成要求**:
                一、核心总结
                1)关键业绩两亮点
                    - 近期核心指标达成情况（如营收/利润/用户增长等）
                    - 对比目标/同期的增长/下滑关键数据
                2)核心问题概述
                    - 当前业务面临的最大挑战（如转化率下降、客户流失等）
                    - 需优先关注的风险点（如供应链延迟、成本超支等）
                3)结论性洞察
                    - 从数据中提炼的1-3个核心结论（例：某区域市场潜力未释放）

                二、数据分析
                    - 根据用户的问题及其数据来选择数据分析的方向例如市场表现分析、客户行为分析、产品分析、运营效率分析、竞争对比分析等
                    - 小标题用1), 2)

                三、行动建议(按照优先级排序)
                    优先级标准：按影响范围和实施难度等维度划分
                    1)高优先级(短期见效)
                    2)中优先级(中期策略)
                    3)长期优先级(战略级)     

                **重要提醒**:
                - 保证格式段落的美观，分段落阐述
                - 文末说明本数据分析报告由AI生成  
                - 生成的文本中不要包含'-'   
                - 生成的子标题必须类似1),2)的样式,不能用纯数字作为小标题的序号      
                """
                stream = client.chat.completions.create(
                    model="deepseek-r1",
                    messages=[{'role': 'user', 'content': analysis_prompt}],
                    stream=True
                )  # 选用deepseek-r1模型流式输出数据分析报告

                full_analysis = ""
                for chunk in stream:
                    if chunk.choices[0].delta.content:
                        chunk_content = chunk.choices[0].delta.content
                        full_analysis += chunk_content
                        yield f"event: analysis_chunk\ndata: {json.dumps({'chunk': chunk_content})}\n\n"

                formatted_analysis = full_analysis
                yield f"event: analysis_complete\ndata: {json.dumps({'analysis': formatted_analysis})}\n\n"
                return

            # 用户输入问题不在缓存当中则调用大模型生成sql和echarts
            sql = MyVanna.generate_sql(question)
            yield f"event: sql\ndata: {json.dumps({'sql': sql})}\n\n"

            data = MyVanna.run_sql(sql)
            yield f"event: table\ndata: {data.to_json(orient='records')}\n\n"

            echarts_prompt = f"""
            你是一个专业的BI工程师，请严格按照以下要求生成ECharts 5.4.3版本的配置JSON：

            **输入数据**:
            问题: {question}
            数据: {data.to_dict(orient='records')}

            **生成要求**:
            1. 输出必须是纯JSON格式，符合以下规范：
                - 使用双引号
                - 无注释
                - 无尾随逗号
                - 无JSON代码块标记(如```json)
                - 字符串中的双引号必须转义为\\"

            2. 图表类型选择逻辑：
                [战区占比]->饼图 | [时间趋势]->折线图 | [类别对比]->柱状图 | [分布]->直方图

            3. 必须包含的字段：
                - title: {{"text": "简明标题"}}
                - tooltip: {{"trigger": "item"或"axis"}}
                - legend: {{"data": [...]}}
                - 至少一个series

            4. 数据格式处理：
                - 字符串值必须用双引号括起来
                - 特殊字符必须转义
                - 数值不添加引号

            5. 图表元素
                - 必须包含标题（反映问题内容）
                - 轴标签使用可读名称（禁用id/代码类字段）
                - 保证图表的美观性，图表上的标签不能折叠

            6. 错误预防：
                - 检查所有字符串引号闭合
                - 检查所有大括号闭合
                - 验证数值类型正确

            **正确示例**:
            {{
                "title": {{"text": "销售数据"}},
                "tooltip": {{"trigger": "axis"}},
                "xAxis": {{
                    "type": "category",
                    "data": ["华东","华北","华南"]
                }},
                "yAxis": {{"type": "value"}},
                "series": [{{
                    "data": [120, 200, 150],
                    "type": "bar"
                }}]
            }}

            **重要提醒**:
                - 你生成的必须是可直接解析的严格JSON
                - 不要包含任何非JSON内容
                - 字符串中如有双引号必须转义
                - 最后检查JSON格式是否正确
                - 如果数据量超过10条，则默认选取前10条数据展示
            """
            completion = client.chat.completions.create(
                model="deepseek-v3",
                messages=[{'role': 'user', 'content': echarts_prompt}]
            )
            echarts_code = data_clean.parse_echarts_code(completion.choices[0].message.content)
            yield f"event: echarts\ndata: {json.dumps(echarts_code)}\n\n"

            # 流式生成分析报告
            analysis_prompt = f"""
            我们是无锡新格尔门窗有限公司，一家专注于门窗研发、生产与销售的企业，主要服务于建筑装饰和家居装修市场。
            你是一个资深商业数据分析师，擅长从数据中提炼业务洞察。请根据以下问题、数据和图表，结合我们公司的情况生成一份结构化的商业分析报告：

            **输入数据**:
            问题: {question}
            数据: {data}
            图表配置: {echarts_code}

            **生成要求**:
            一、核心总结
            1)关键业绩两亮点
                - 近期核心指标达成情况（如营收/利润/用户增长等）
                - 对比目标/同期的增长/下滑关键数据
            2)核心问题概述
                - 当前业务面临的最大挑战（如转化率下降、客户流失等）
                - 需优先关注的风险点（如供应链延迟、成本超支等）
            3)结论性洞察
                - 从数据中提炼的1-3个核心结论（例：某区域市场潜力未释放）

            二、数据分析
                - 根据用户的问题及其数据来选择数据分析的方向例如市场表现分析、客户行为分析、产品分析、运营效率分析、竞争对比分析等
                - 小标题用1), 2)

            三、行动建议(按照优先级排序)
                优先级标准：按影响范围和实施难度等维度划分
                1)高优先级(短期见效)
                2)中优先级(中期策略)
                3)长期优先级(战略级)     

            **重要提醒**:
            - 保证格式段落的美观，分段落阐述
            - 文末说明本数据分析报告由AI生成  
            - 生成的文本中不要包含'-'    
            """
            stream = client.chat.completions.create(
                model="deepseek-r1",
                messages=[{'role': 'user', 'content': analysis_prompt}],
                stream=True
            )

            # 功能同缓存匹配成功的情况
            full_analysis = ""
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    chunk_content = chunk.choices[0].delta.content
                    full_analysis += chunk_content
                    yield f"event: analysis_chunk\ndata: {json.dumps({'chunk': chunk_content})}\n\n"

            formatted_analysis = full_analysis
            yield f"event: analysis_complete\ndata: {json.dumps({'analysis': formatted_analysis})}\n\n"

            # 连接数据库，当用户输入一个问题时默认将生成的结果标记正确然后插入本地数据库
            connection = pymysql.connect(
                host='kphone01o.mysql.rds.aliyuncs.com',
                user='aitemp_admin',
                password='aitemp-admin123',
                port=3306,
                db='ai_report_error_feedback',
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            with connection.cursor() as cursor:
                insert_sql = """
                INSERT INTO ai_report_error_feedback.cm_report_error_feedback 
                (`time`, question, `sql`, echarts_code, user_feedback, if_result_true, if_result_cache)
                VALUES (NOW(), %s, %s, %s, NULL, 1, 0)
                """
                cursor.execute(insert_sql, (
                    question,
                    sql,
                    json.dumps(echarts_code, indent=2)
                ))
            connection.commit()
            connection.close()
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "event: done\ndata: {}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


# 用户反馈功能
@app.route('/feedback', methods=['POST'])
def handle_feedback():
    data = request.json
    try:
        connection = pymysql.connect(
            host='kphone01o.mysql.rds.aliyuncs.com',
            user='aitemp_admin',
            password='aitemp-admin123',
            port=3306,
            db='ai_report_error_feedback',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,  # 连接超时时间(秒)
            read_timeout=10,  # 读取超时时间(秒)
            write_timeout=10  # 写入超时时间(秒)
        )
        with connection.cursor() as cursor:
            sql = """
            INSERT INTO ai_report_error_feedback.cm_report_error_feedback 
            (`time`, question, `sql`, echarts_code, user_feedback, if_result_true, if_result_cache)
            VALUES (NOW(), %s, %s, NULL, %s, %s, 0)
            """
            cursor.execute(sql, (
                data['question'],
                data['sql'],
                data.get('feedback'),
                data.get('is_correct')
            ))
        connection.commit() # 当用户反馈结果有问题时将数据及用户反馈插入数据库并且标记问题答案错误
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if connection:
            connection.close()


# 为添加缓存的函数配置路由从而便于配定时任务
@app.route('/update-cache', methods=['GET'])
def trigger_cache_update():
    try:
        add_cache.update_cache()
        return {"status": "success", "message": "update_cache_success"}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=9092)
    # VannaFlaskApp(MyVanna).run()
