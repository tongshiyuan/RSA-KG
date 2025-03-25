import time
import base64
import asyncio
from volcenginesdkarkruntime import AsyncArk, Ark

vision_model = ""
chat_model = ''
api_key = ''
client = Ark(api_key=f"{api_key}")
async_client = AsyncArk(api_key=f"{api_key}")
MAX_CONCURRENT_REQUESTS = 10
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def find_image_paths(data, paths=None):
    """
    递归查找JSON数据中的'image_path'和对应的'type'，当'type' == 'table'时保存。

    :param data: 当前的JSON数据，可以是字典、列表或其他类型
    :param paths: 用于存储找到的(type, image_path)元组
    :return: 包含符合条件的(type, image_path)的列表
    """
    if paths is None:
        paths = []

    if isinstance(data, dict):
        # 如果当前数据是字典，检查其中是否有 'image_path' 和 'type'
        image_path = data.get("image_path")
        item_type = data.get("type")
        # 当 'type' 为 'table' 且有 'image_path' 时，保存该路径
        if item_type == "table" and image_path:
            paths.append((item_type, image_path))
        if item_type == "image" and image_path:
            paths.append((item_type, image_path))
        # 递归遍历字典中的所有子项
        for key, value in data.items():
            find_image_paths(value, paths)

    elif isinstance(data, list):
        # 如果当前数据是列表，遍历列表中的每一项
        for item in data:
            find_image_paths(item, paths)

    return paths


def chat_with_image(Prompt, image_path):
    # 需要传给大模型的图片
    # image_path = "path_to_your_image.jpg"
    # 将图片转为Base64编码
    base64_image = encode_image(image_path)
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": Prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    # 需要注意：传入Base64编码前需要增加前缀 data:image/{图片格式};base64,{Base64编码}
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
            )
            msg = response.choices[0].message.content.replace('$', '').replace('\\', '')
            if "I'm unable to answer that question" in msg:
                return 'System Error'
            return msg
        except Exception as e:
            if attempt == 4:
                return f'Failed to generate step after 5 attempts. Error: {str(e)}"'
            if "Error code: 429" in str(e):
                time.sleep(60)


async def async_chat_with_image(task_id, Prompt, image_path):
    # 需要传给大模型的图片
    # image_path = "path_to_your_image.jpg"
    # 将图片转为Base64编码
    base64_image = encode_image(image_path)
    async with semaphore:
        for attempt in range(5):
            try:
                response = await async_client.chat.completions.create(
                    model=vision_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": Prompt,
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        # 需要注意：传入Base64编码前需要增加前缀 data:image/{图片格式};base64,{Base64编码}
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                )
                msg = response.choices[0].message.content.replace('$', '').replace('\\', '')
                if "I'm unable to answer that question" in msg:
                    return 'System Error'
                return task_id, msg
            except Exception as e:
                if attempt == 4:
                    return task_id, f'Failed to generate step after 5 attempts. Error: {str(e)}"'
                if "Error code: 429" in str(e):
                    await asyncio.sleep(60)


def chat_without_image(messages, is_final_answer=False):
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model=chat_model,
                messages=messages,
                temperature=0.01,
                top_p=0.7,
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return response_content
        except Exception as e:
            if attempt == 4:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return response_content
            if "Error code: 429" in str(e):
                time.sleep(60)


async def async_chat_without_image(task_id, messages, chat_model, is_final_answer=False):
    async with semaphore:
        for attempt in range(5):
            try:
                response = await async_client.chat.completions.create(
                    model=chat_model,
                    messages=messages,
                    temperature=0.01,
                    top_p=0.7,
                )
                response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
                if "I'm unable to answer that question" in response_content:
                    response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
                # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
                return task_id, response_content
            except Exception as e:
                if attempt == 4:
                    if is_final_answer:
                        response_content = f'''{{"title": "Error",
                            "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                    else:
                        response_content = f'''{{"title": "Error",
                            "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                            "next_action": "final_answer"}}'''
                    return task_id, response_content
                if "Error code: 429" in str(e):
                    await asyncio.sleep(60)


async def async_response(sessions):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_image(session_id, session['prompt'], session['img_path'], chat_model))
    results = await asyncio.gather(*tasks)
    return results


async def async_response_chat(sessions, chat_model='ep-20250123184253-lmglw'):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_without_image(session_id, session, chat_model))
    results = await asyncio.gather(*tasks)
    return results


async def llm_read_image(image_path, raw_parse, html=False):
    # 需要传给大模型的图片
    # image_path = "path_to_your_image.jpg"
    if html:
        Prompt = f'''你是一位专业的表格识别专家，负责提取复杂流行病学研究表格中的文字内容，并将其保留原有从属关系，转换为HTML格式。  

请仔细阅读以下通过其他方法提取的表格内容（仅供参考，结果准确性需核实）：  
<raw_parse>  
{raw_parse}  
</raw_parse>  

在提取和转换表格内容时，请严格遵循以下要求：  

1. **准确提取内容**：全面准确地提取表格中的所有文字内容，确保不遗漏任何信息。由于这是复杂的流行病学研究表格，请特别注意保持内容的完整性和结构。  
2. **转换为HTML格式**：根据表格结构，正确使用HTML标签（如 `<table>`、`<tr>`、`<td>` 等）构建表格。  
   - 每一行用 `<tr>` 标签表示。  
   - 每个单元格用 `<td>` 标签表示（若有表头，用 `<th>` 标签）。  
   - 如果表格有合并单元格，使用 `rowspan` 和 `colspan` 属性准确标识。  

请直接输出最终的HTML表格代码，不要添加任何额外说明或内容。'''
    else:
        Prompt = f'''你是一位专业的表格识别专家，负责提取表格中的文字内容并将其转换为Markdown格式。  

# 规则：  
1. 在识别表格内容时，务必考虑表格的结构和内容，准确完整地提取所有文字信息。  
2. 不对结果进行翻译或解释，仅输出提取后的表格内容。  
3. 由于这是复杂的流行病学研究表格，请特别仔细处理，确保内容无误。  
4. 下方是通过其他方法提取的表格内容，仅供参考，但其准确性需核实。  

# 参考：  
<raw_parse>  
{raw_parse}  
</raw_parse>  

# 输出：  
请直接输出Markdown格式的表格作为最终结果，不要添加任何多余说明或内容。'''
    # 将图片转为Base64编码
    base64_image = encode_image(image_path)
    for attempt in range(5):
        try:
            response = await async_client.chat.completions.create(
                model=vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": Prompt,
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    # 需要注意：传入Base64编码前需要增加前缀 data:image/{图片格式};base64,{Base64编码}
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
            )
            msg = response.choices[0].message.content.replace('$', '').replace('\\', '')
            if "I'm unable to answer that question" in msg:
                return 'System Error'
            return msg
        except Exception as e:
            if attempt == 4:
                return f'Failed to generate step after 5 attempts. Error: {str(e)}"'
            if "Error code: 429" in str(e):
                await asyncio.sleep(60)


async def async_response_with_llama(sessions, Sema=10):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_llama(session_id, session))
    # results = await asyncio.gather(*tasks)
    semaphore = asyncio.Semaphore(Sema)
    async with semaphore:
        results = await asyncio.gather(*tasks)
        await asyncio.sleep(30)
    return results



async def async_chat_with_llama(session_id, session, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    chat_model = "Pro/meta-llama/Meta-Llama-3.1-8B-Instruct"
    api_key = ''
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
    for attempt in range(5):
        try:
            response = await client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 4:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 429" in str(e):
                asyncio.sleep(60)


async def async_response_with_deepseek(sessions, model='v3'):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_deepseek(session_id, session, model))
    results = await asyncio.gather(*tasks)
    return results


async def async_chat_with_deepseek(session_id, session, model, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    if model == 'v3':
        chat_model = "deepseek-chat"
    elif model == 'r1':
        chat_model = "deepseek-reasoner"
    else:
        print('无法识别该模型，请输入v3或r1')
    api_key = ''
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1/")
    for attempt in range(5):
        try:
            response = await client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 4:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 429" in str(e):
                asyncio.sleep(60)

async def async_response_with_qwen(sessions):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_qwen(session_id, session))
    results = await asyncio.gather(*tasks)
    return results


async def async_chat_with_qwen(session_id, session, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    chat_model = "qwen-max"
    api_key = ''
    # chat_model = "Pro/meta-llama/Meta-Llama-3.1-8B-Instruct"
    client = AsyncOpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
    for attempt in range(5):
        try:
            response = await client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 4:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 400" in str(e):
                asyncio.sleep(60)

async def async_response_with_deepseek_sc(sessions, model='v3'):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_deepseek_sc(session_id, session, model))
    results = await asyncio.gather(*tasks)
    return results


async def async_chat_with_deepseek_sc(session_id, session, model, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    if model == 'v3':
        chat_model = "deepseek-ai/DeepSeek-V3"
    elif model == 'r1':
        chat_model = "deepseek-ai/DeepSeek-R1"
    else:
        print('无法识别该模型，请输入v3或r1')
    api_key = ''
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.siliconflow.cn/v1")
    for attempt in range(5):
        try:
            response = await client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 4:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 429" in str(e):
                asyncio.sleep(60)


async def async_response_with_gpt4o(sessions, Sema=10):
    tasks = []
    for session_id, session in sessions.items():
        tasks.append(async_chat_with_gpt4o(session_id, session))
    semaphore = asyncio.Semaphore(Sema)
    async with semaphore:
        results = await asyncio.gather(*tasks)
        await asyncio.sleep(20)
    return results


async def async_chat_with_gpt4o(session_id, session, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    model = 'chatgpt-4o-latest'
    api_key = ''
    client = AsyncOpenAI(api_key=api_key, base_url="https://api.302.ai/v1")
    for attempt in range(3):
        try:
            response = await client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 2:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 429" in str(e):
                asyncio.sleep(60)

def response_with_gpt4o(sessions, slp=10):
    results = []
    for session_id, session in sessions.items():
        results.append(chat_with_gpt4o(session_id, session))
        time.sleep(slp)
    return results


def chat_with_gpt4o(session_id, session, is_final_answer=False):
    from openai import OpenAI, AsyncOpenAI
    model = 'chatgpt-4o-latest'
    api_key = ''
    client = OpenAI(api_key=api_key, base_url="https://api.302.ai/v1")
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=chat_model,
                messages=session
            )
            response_content = ' '.join(response.choices[0].message.content.replace('，', ',').split())
            if "I'm unable to answer that question" in response_content:
                response_content = '{"title": "Error", "content": "System Error", "next_action": "final_answer"}'
            # response_content = response_content.lstrip('<answer> ').rstrip('</answer>')
            return session_id, response_content
        except Exception as e:
            if attempt == 2:
                if is_final_answer:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate final answer after 5 attempts. Error: {str(e)}"}}'''
                else:
                    response_content = f'''{{"title": "Error",
                        "content": "Failed to generate step after 5 attempts. Error: {str(e)}",
                        "next_action": "final_answer"}}'''
                return session_id, response_content
            if "Error code: 429" in str(e):
                time.sleep(60)