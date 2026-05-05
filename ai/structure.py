from typing import List

from pydantic import BaseModel, Field, field_validator
import re

class Structure(BaseModel):
    tldr: str = Field(description="一句紧凑概括，说明论文在研究方向中的定位，不要复述摘要。若语言为中文，除专有名词外必须使用中文。")
    motivation: List[str] = Field(description="必须输出2-4个数组元素，不得少于2个；每个元素最多一行；只描述已有工作的缺口、瓶颈或不足，不混入本文方法。若语言为中文，除专有名词外必须使用中文。")
    method: List[str] = Field(description="必须输出3-5个数组元素：第1个元素概括核心思路，后续2-4个元素描述最本质的贡献或技术动作，并说明相比已有工作的关键新意。若语言为中文，除专有名词外必须使用中文。")
    result: str = Field(description="只描述验证范围和主要实验结论；说明任务类型、benchmark、多任务或多场景验证，以及是否包含真实世界验证；不列具体数字、不描述表格、不写消融。若语言为中文，除专有名词外必须使用中文。")
    conclusion: List[str] = Field(description="必须输出1-3个数组元素，包含核心价值、主要限制和关键takeaway；限制要写深层问题，不写空泛的更多实验。若语言为中文，除专有名词外必须使用中文。")
