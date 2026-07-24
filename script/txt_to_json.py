"""
将doc目录下的txt法律文档转换为JSON格式
类似于 xianfa.txt -> xianfa.json 的转换
"""

import json
import re
from pathlib import Path


def generate_id(law_code: str, article_num: str, index: int) -> str:
    """生成条款ID"""
    # 处理序言等特殊编号
    if "序" in article_num:
        num_str = "0000"
    else:
        # 提取数字
        nums = re.findall(r'\d+', article_num)
        num_str = nums[0] if nums else str(index).zfill(4)
        num_str = num_str.zfill(4)
    
    return f"{law_code}_001_001_{num_str}"


def extract_tags(content: str, law_name: str) -> list:
    """根据内容自动生成标签"""
    tags = [law_name]
    
    # 关键词匹配
    keywords = {
        "劳动": ["劳动法", "劳动者权益"],
        "合同": ["合同", "劳动合同"],
        "保险": ["社会保险", "保险"],
        "工资": ["工资", "报酬"],
        "退休": ["退休", "养老金"],
        "工伤": ["工伤", "职业病"],
        "妇女": ["妇女权益", "性别平等"],
        "未成年": ["未成年人", "童工"],
        "选举": ["选举权", "政治权利"],
        "宗教": ["宗教信仰"],
        "教育": ["教育", "受教育权"],
        "婚姻": ["婚姻", "家庭"],
        "继承": ["继承", "遗产"],
        "离婚": ["离婚"],
        "收养": ["收养"],
        "法人": ["法人", "非法人组织"],
        "物权": ["物权", "所有权", "用益物权", "担保物权"],
        "侵权": ["侵权", "损害赔偿", "侵权责任"],
        "补偿": ["补偿", "征收", "征用"],
        "财产": ["私有财产", "公共财产"],
        "公民": ["公民", "基本权利"],
        "平等": ["平等", "歧视"],
    }
    
    for keyword, related_tags in keywords.items():
        if keyword in content:
            for tag in related_tags:
                if tag not in tags:
                    tags.append(tag)
    
    return tags[:5]  # 最多5个标签


def parse_law_txt(txt_path: str) -> dict:
    """解析法律txt文件"""
    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    # 1. 提取法律名称（第一行）
    law_name = lines[0].strip()
    
    # 2. 提取颁布时间和通过会议
    publish_time = None
    meeting = None
    
    title_line = lines[1] if len(lines) > 1 else ""
    # 匹配日期: 1994年7月5日
    date_match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', title_line)
    if date_match:
        publish_time = date_match.group(1)
    
    # 匹配会议
    conf_match = re.search(r'第[一二三四五六七八九十百]+届全国', title_line)
    if conf_match:
        meeting = conf_match.group(0)
    
    # 3. 提取目录
    toc = []
    in_toc = False
    
    for i, line in enumerate(lines):
        line = line.strip()
        if "目　　录" in line:
            in_toc = True
            continue
        if in_toc:
            # 遇到章节名
            if re.match(r'^[第章节]+', line) and line:
                toc.append({"章节": line, "级别": "章"})
            elif re.match(r'第一章|第二章|第三章|第四章|第五章|第六章|第七章', line):
                toc.append({"章节": line, "级别": "章"})
            elif re.search(r'第[一二三四五六七八九十百]+节', line):
                toc.append({"章节": line, "级别": "节"})
            
            # 遇到实际条款内容，目录结束
            if line and "第一条" in line:
                in_toc = False
    
    # 4. 提取条款
    clauses = []
    law_code = get_law_code(law_name)
    
    # 条款匹配模式：第X条 或者 附则
    article_pattern = r'^(第[一二三四五六七八九十百零〇\\d]+条|附　　则|附　　则)'
    
    current_article_num = None
    current_content_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # 检查是否是条款开始
        match = re.match(article_pattern, line_stripped)
        if match:
            # 保存上一条
            if current_article_num:
                content_text = '\n'.join(current_content_lines).strip()
                # 分离编号和内容
                if content_text.startswith(current_article_num):
                    content_text = content_text[len(current_article_num):].strip()
                
                if content_text:
                    clauses.append({
                        "编号": current_article_num,
                        "内容": content_text,
                        "id": generate_id(law_code, current_article_num, len(clauses) + 1),
                        "标签": extract_tags(content_text, law_name)
                    })
            
            current_article_num = match.group(0)
            current_content_lines = [line_stripped]
        elif current_article_num:
            current_content_lines.append(line_stripped)
    
    # 保存最后一条
    if current_article_num:
        content_text = '\n'.join(current_content_lines).strip()
        if content_text.startswith(current_article_num):
            content_text = content_text[len(current_article_num):].strip()
        
        if content_text:
            clauses.append({
                "编号": current_article_num,
                "内容": content_text,
                "id": generate_id(law_code, current_article_num, len(clauses) + 1),
                "标签": extract_tags(content_text, law_name)
            })
    
    # 构建结果
    result = {
        "法律名称": law_name,
        "条款": clauses
    }
    
    if publish_time:
        result["颁布时间"] = publish_time
    if meeting:
        result["通过会议"] = meeting
    if toc:
        result["目录"] = toc
    
    return result


def get_law_code(law_name: str) -> str:
    """根据法律名称生成代码"""
    name_to_code = {
        "宪法": "XC",
        "民法典": "CC",
        "刑法": "XF",
        "劳动法": "LD",
        "劳动合同法": "LD",
        "公司法": "GS",
        "婚姻法": "HY",
        "保险法": "BX",
        "合同法": "HT",
    }
    
    for key, code in name_to_code.items():
        if key in law_name:
            return code
    
    # 默认使用拼音首字母
    return "LW"


def convert_txt_to_json(txt_path: str, output_path: str = None) -> dict:
    """转换单个txt文件为json"""
    if output_path is None:
        output_path = Path(txt_path).with_suffix('.json')
    
    result = parse_law_txt(txt_path)
    
    # 写入JSON文件
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result


if __name__ == "__main__":
    import glob
    
    doc_dir = r"c:\Users\echuzhi\repo\legal-agent\doc"
    output_dir = r"c:\Users\echuzhi\repo\legal-agent\web-chat-app\backend\legal_konwlegde"
    
    # 处理所有txt文件
    txt_files = glob.glob(f"{doc_dir}/*.txt")
    
    print(f"找到 {len(txt_files)} 个 txt 文件\n")
    
    for txt_file in sorted(txt_files):
        txt_path = Path(txt_file)
        
        # 跳过已存在的json文件对应的源
        if txt_path.stem in ["minfadian", "xianfa", "xingfa"]:
            print(f"跳过: {txt_path.name} (已有对应json)")
            continue
        
        output_path = f"{output_dir}\\{txt_path.stem}.json"
        
        print(f"处理: {txt_path.name}")
        try:
            result = convert_txt_to_json(txt_file, output_path)
            print(f"  -> 已保存到: {txt_path.stem}.json ({len(result.get('条款', []))} 个条款)\n")
        except Exception as e:
            print(f"  -> 错误: {e}\n")