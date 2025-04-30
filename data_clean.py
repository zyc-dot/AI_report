import json
import re


def parse_echarts_code(raw_content):
    """安全解析ECharts代码"""
    try:
        # 尝试直接解析
        return json.loads(raw_content)
    except json.JSONDecodeError as e:
        print(f"第一次解析失败: {e}")

        # 尝试清理内容
        clean_content = raw_content.strip()

        # 去除可能的代码块标记
        if clean_content.startswith('```json'):
            clean_content = clean_content[7:]
        if clean_content.startswith('```'):
            clean_content = clean_content[3:]
        if clean_content.endswith('```'):
            clean_content = clean_content[:-3]
        clean_content = clean_content.strip()

        # 处理常见的格式问题
        clean_content = clean_content.replace("'", '"')  # 单引号转双引号
        clean_content = re.sub(r'//.*?\n', '', clean_content)  # 去除单行注释
        clean_content = re.sub(r'/\*.*?\*/', '', clean_content, flags=re.DOTALL)  # 去除多行注释

        # 尝试自动修复未闭合的引号
        lines = clean_content.split('\n')
        for i, line in enumerate(lines):
            if line.count('"') % 2 != 0:
                lines[i] = line + '"'
        clean_content = '\n'.join(lines)

        try:
            return json.loads(clean_content)
        except json.JSONDecodeError as e:
            print(f"自动修复后仍然失败: {e}")
            # 作为最后手段，尝试提取第一个完整JSON对象
            match = re.search(r'\{.*\}', clean_content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            raise ValueError("无法解析生成的ECharts配置，请检查提示词")


def clean_and_format_text(text):
    # 去除Markdown标记（#、**、---等）
    text = re.sub(r'#+\s*', '', text)  # 去除标题标记
    text = re.sub(r'\*{2}(.*?)\*{2}', r'\1', text)  # 去除加粗标记
    text = re.sub(r'-{3,}', '', text)  # 去除分隔线

    # 去除其他特殊字符（保留中文、英文、数字、标点和换行）
    text = re.sub(r'[^\w\u4e00-\u9fff%，。；：()、\n\r\t]', '', text)

    # 确保最后一行单独换行显示
    if "本数据分析报告由AI生成" in text:
        parts = text.split("本数据分析报告由AI生成")
        text = parts[0].strip() + "\n\n本数据分析报告由AI生成" + parts[1]

    # 分段处理
    sections = []
    current_section = []

    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue

        # 检测是否是新的主标题（如"一、核心总结"）
        if re.match(r'^[一二三四五六七八九十]、', line):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
            current_section.append(f"\n{line}")
        # 检测是否是子标题（如"1. 关键业绩亮点"）
        elif re.match(r'^\d+\.\s', line):
            if current_section:
                sections.append('\n'.join(current_section))
                current_section = []
            current_section.append(f"\n{line}\n")
        else:
            current_section.append(line)

    if current_section:
        sections.append('\n'.join(current_section))

    return '\n'.join(sections)


def dict_to_text(data, indent=0):
    lines = []
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append("  " * indent + f"{key}:")
            lines.append(dict_to_text(value, indent + 1))
        else:
            lines.append("  " * indent + f"{key}: {value}")
    return "\n".join(lines)
