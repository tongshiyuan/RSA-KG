import os
import re
from .llm import llm_read_image, async_response
from .prompts import table_prompts, figure_prompts


# 切割 markdown 文件， 为每个paragraph提取上级结构
class Paragraph:
    def __init__(self, content, headers):
        self.content = content  # 段落内容
        self.headers = headers  # 标题层级列表，最多支持6个层级
        self.length = len(content)  # 计算content的字符长度

    def __repr__(self):
        return f"Paragraph(content={self.content[:50]}..., headers={self.headers}, length={self.length})"

    def append_content(self, new_content):
        """合并新内容到当前段落的content中，并更新字符长度"""
        self.content += "\n" + new_content
        self.length = len(self.content)  # 更新字符长度


class MarkdownParser:
    def __init__(self, markdown_text, a=1200, b=3000):
        self.markdown_text = markdown_text
        self.a = a  # 合并条件：content长度小于a
        self.b = b  # 合并后content最大长度不超过b
        self.paragraphs = []  # 存储所有的段落
        self.parse_markdown()

    def parse_markdown(self):
        # 按正则表达式匹配标题层级
        header_pattern = re.compile(r"^(#{1,6})\s*(.*?)\s*$", re.MULTILINE)

        # 匹配所有标题
        matches = list(re.finditer(header_pattern, self.markdown_text))

        last_pos = 0  # 记录当前段落起始位置
        level_headers = [None] * 6  # 最多支持6个标题层级

        for i, match in enumerate(matches):
            header_level = len(match.group(1))  # 标题的层级，1到6
            header_text = match.group(2)  # 标题文本

            # 更新标题层级
            level_headers[header_level - 1] = header_text

            # 找到段落内容，使用下一个标题的位置作为结束标志
            header_pos = match.start()
            if i == len(matches) - 1:  # 如果是最后一个标题
                content = self.markdown_text[last_pos:].strip()
            else:
                next_header_pos = matches[i + 1].start()
                content = self.markdown_text[last_pos:next_header_pos].strip()

            # 过滤掉标题行，只保留段落内容
            content_lines = content.split("\n")
            content_lines = [line for line in content_lines if not line.startswith("#")]  # 去掉以#开头的行
            content = "\n".join(content_lines).strip()  # 合并剩下的行作为段落内容

            # 如果内容为空，则跳过该段落
            if not content:
                continue

            # 创建一个新的段落对象
            paragraph = Paragraph(content, level_headers[:header_level])  # 只保存到当前层级

            # 检查是否需要合并
            self.merge_paragraph(paragraph)

            # 保存当前段落
            self.paragraphs.append(paragraph)

            last_pos = match.end()  # 更新段落开始位置

    def merge_paragraph(self, new_paragraph):
        """合并拥有相同header的段落"""
        for paragraph in self.paragraphs:
            if paragraph.headers == new_paragraph.headers:
                # 如果content长度小于a且合并后不超过b，则进行合并
                if new_paragraph.length < self.a and (paragraph.length + new_paragraph.length) <= self.b:
                    paragraph.append_content(new_paragraph.content)
                    return  # 合并后不需要再加入新段落
        # 如果没有找到合并的段落，直接加入新的段落
        return

    def get_paragraphs(self):
        return self.paragraphs


def extract_image_paths(markdown_text, prompt_dict, file_path, content_chunk=3):
    '''
    从markdown文件中找图片，并返回上下文
    :param markdown_text:
    :param prompt_dict:
    :param file_path:
    :param content_chunk:
    :return:
    '''
    img_dict = {}
    image_pattern = r'!\[.*?\]\((.*?)\)'
    image_paths = re.findall(image_pattern, markdown_text)
    if image_paths:
        for img in image_paths:
            [chunk_up, chunk_down] = markdown_text.split(f'![]({img})')
            chunk_use = chunk_up.split('\n\n')[-content_chunk:]
            chunk_use += chunk_down.split('\n\n')[:content_chunk]
            chunk_content = "\n".join(chunk_use)
            if 'fig' in img.lower():
                img_dict[img.split('/')[1].split('.')[0]] = {'img_type': 'figure', 'img_path': f'{file_path}/{img}',
                                                             'prompt': prompt_dict['figure'].render(
                                                                 chunk_content=chunk_content)}
            elif 'table' in img.lower():
                img_dict[img.split('/')[1].split('.')[0]] = {'img_type': 'table', 'img_path': f'{file_path}/{img}',
                                                             'prompt': prompt_dict['table'].render(
                                                                 chunk_content=chunk_content)}
            else:
                print(f'error: {img}')
    return img_dict


import os
import cv2
import html2text
from rapid_table import RapidTable, RapidTableInput
from rapidocr_onnxruntime import RapidOCR


def get_rotate_angle(img_path):
    import subprocess
    # Construct the Tesseract command
    platform = os.uname()[0]
    if platform == 'Darwin':
        psm = '--psm'
    else:
        psm = '-psm'
    command = f'tesseract {img_path} stdout {psm} 0'
    # Execute the command
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # Check for errors
    if result.returncode != 0:
        print(f"Error processing {img_path}: {result.stderr.strip()}")
        return None
    # Parse the output to extract the orientation angle
    for line in result.stdout.splitlines():
        if 'Rotate:' in line:
            angle = line.split(':')[-1].strip()
            return angle
    print(f"Failed to detect angle for {img_path}")
    return None


def rotation(img, angle):
    if angle:
        angle = int(angle)
        if angle < 10:
            return img
        elif angle > 80 and angle < 100:
            rotated_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            return rotated_img
        elif angle > 170 and angle < 190:
            rotated_img = cv2.rotate(img, cv2.ROTATE_180)
            return rotated_img
        elif angle > 260 and angle < 280:
            rotated_img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            return rotated_img
    else:
        return None


def perform_ocr(img_path, img_orientation=True, html=False):
    img = cv2.imread(img_path)
    if img_orientation:
        from wired_table_rec.utils import ImageOrientationCorrector
        img_orientation_corrector = ImageOrientationCorrector()
        img = img_orientation_corrector(img)
        angle = get_rotate_angle(img_path)
        rotated_img = rotation(img, angle)
        img = rotated_img

    # input_args = RapidTableInput(model_type="unitable")
    # table_engine = RapidTable(input_args)
    # table_engine = RapidTable()
    input_args = RapidTableInput()
    table_engine = RapidTable(input_args)

    ocr_engine = RapidOCR(
        det_model_dir="/Users/bytedance/Desktop/workplace/High_risk_factors/scripts/table_rec/models/ch_PP-OCRv4_det_server_infer.onnx",
        rec_model_dir="/Users/bytedance/Desktop/workplace/High_risk_factors/scripts/table_rec/models/ch_PP-OCRv4_rec_server_infer.onnx")
    ocr_res, _ = ocr_engine(img)
    table_results = table_engine(img, ocr_result=ocr_res)
    table_html_str = table_results.pred_html
    if html:
        return table_html_str
    markdown = html2text.html2text(table_html_str)
    return markdown


def merge_chunks(strings, min_length=500, max_length=1200):
    """
    合并字符串列表中的元素，确保任意相邻两个元素的长度和不小于1200。
    参数：
        strings (list): 包含字符串的列表。
    返回：
        list: 合并后的字符串列表。
    """
    # 检查输入是否为空
    if not strings:
        return []

    # 初始化结果列表
    result = []

    # 初始化当前合并字符串
    current_string = ""

    for string in strings:
        # 检查当前字符串长度是否小于500
        if len(string) < min_length:
            # 尝试合并到当前字符串
            if len(current_string) + len(string) < max_length:
                current_string += "\n" + string if current_string else string
            else:
                # 当前字符串长度已经达到要求，保存并重置
                result.append(current_string)
                current_string = string
        else:
            # 当前字符串长度>=500，先保存当前字符串
            if current_string:
                result.append(current_string)
                current_string = ""
            result.append(string)

    # 最后检查是否有未保存的字符串
    if current_string:
        result.append(current_string)

    # 确保所有相邻元素满足要求
    while len(result) > 1:
        merged = False
        for i in range(len(result) - 1):
            if len(result[i]) + len(result[i + 1]) < max_length:
                result[i] += "\n" + result[i + 1]
                del result[i + 1]
                merged = True
                break
        if not merged:
            break

    return result


async def get_parsed_md(base_path, out_file):
    # base_path = 'raw_file/1.神经放射综述/'
    raw_text_content = open(os.path.join(base_path, f'Text.md'), 'r', encoding='utf-8').read()
    raw_text_content = raw_text_content.replace('\xa0', ' ').replace('\u202f', ' ').replace('\u2002', ' ').replace(
        '\u2009', ' ')
    raw_text_content = re.sub(' +', ' ', raw_text_content)
    raw_text_content = re.sub(' +\n', '\n', raw_text_content)

    prompt_dict = {
        'table': table_prompts,
        'figure': figure_prompts,
    }
    img_summary_session = extract_image_paths(raw_text_content, prompt_dict, base_path)

    summarys = await async_response(img_summary_session)
    summarys_dict = dict(summarys)

    rpl_content = raw_text_content
    for _id, summary in summarys_dict.items():
        summary = summary.replace('\n\n', '\n')
        if img_summary_session[_id]['img_type'] == 'table':
            table_id = img_summary_session[_id]['img_path'].split('/')[-1].split('.')[0]
            if os.path.exists(os.path.join(base_path, f'{table_id}.md')):
                table_md = open(os.path.join(base_path, f'{table_id}.md'), 'r', encoding='utf-8').read()
            else:
                # table ocr
                img_full_path = os.path.join(img_summary_session[_id]['img_path'])
                table_md = perform_ocr(img_full_path, html=None)
                table_md = await llm_read_image(img_full_path, table_md, html=None)
                with open(os.path.join(base_path, f'{table_id}.md'), 'w') as f:
                    f.write(table_md)
            table_md = table_md.replace('\n\n', '\n')
            table_chunk = f'''<summary of table id="{table_id}">
    {summary.strip()}
    </summary of table id="{table_id}">
    <table id="{table_id}">
    {table_md.strip()}
    </table id="{table_id}">'''
            rpl_content = rpl_content.replace(f'![](images/{table_id}.jpg)', table_chunk)
        else:
            figure_id = img_summary_session[_id]['img_path'].split('/')[-1].split('.')[0]
            table_chunk = f'''<summary of figure id="{figure_id}">
    {summary.strip()}
    </summary of figure id="{figure_id}">'''
            rpl_content = rpl_content.replace(f'![](images/{figure_id}.jpg)', table_chunk)

    with open(out_file, 'w') as f:
        f.write(rpl_content)
