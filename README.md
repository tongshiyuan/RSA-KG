RSA-KG
---
This study introduces RSA-KG: A Graph-based Rag enhanced AI Knowledge Graph for Recurrent Spontaneous Abortions Diagnosis and Clinical Decision Support.

The following is the construction process of the knowledge graph:
1. We use [minerU 0.10.6 ](https://github.com/opendatalab/mineru) to parse the text, and export the tables and figures as images.
```shell
magic-pdf -p /our/document/path/ -o /our/outdir
```
- Note: We have manually checked the parsed document to ensure the accuracy of the content, especially the text content and structure, etc.
2. We use [slanet_plus](https://github.com/PaddlePaddle/PaddleX/blob/release/3.0-beta1/docs/module_usage/tutorials/ocr_modules/table_structure_recognition.md) in [RapidTable](https://github.com/RapidAI/RapidTable) to parse the table content.
- Note: In the script operation, we use [tesseract](https://github.com/tesseract-ocr/tesseract) to determine the orientation of the table and rotate it.
3. We use [doubao-vision-pro](https://www.volcengine.com/docs/82379/) visual large language model to correct the results.
4. We perform paragraph segmentation on the entire text content. Combining the paragraphs adjacent to the tables/figures, we use doubao-vision-pro to summarize the information.
5. Merge each paragraph under the document directory structure to make the paragraph length between 1200 and 4800. Add article structure information/document information and mark each chunk. And summarize the chunks in combination with the tables/figures.
6. We use [lightRAG](https://github.com/HKUDS/LightRAG) to build the knowledge base.