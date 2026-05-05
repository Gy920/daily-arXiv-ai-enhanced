from pydantic import BaseModel, Field, field_validator
import re

class Structure(BaseModel):
    tldr: str = Field(description="一句紧凑概括，说明论文在研究方向中的定位，不要复述摘要。若语言为中文，除专有名词外必须使用中文。")
    motivation: str = Field(description="2-4条短要点，每条最多一行；只描述已有工作的缺口、瓶颈或不足，不混入本文方法。若语言为中文，除专有名词外必须使用中文。")
    method: str = Field(description="先用一句话概括核心思路，再给出2-4条短要点；只保留最本质的贡献或技术动作，并说明相比已有工作的关键新意。若语言为中文，除专有名词外必须使用中文。")
    result: str = Field(description="只描述验证范围和主要实验结论；说明任务类型、benchmark、多任务或多场景验证，以及是否包含真实世界验证；不列具体数字、不描述表格、不写消融。若语言为中文，除专有名词外必须使用中文。")
    conclusion: str = Field(description="1-3条短要点，包含核心价值、主要限制和关键takeaway；限制要写深层问题，不写空泛的更多实验。若语言为中文，除专有名词外必须使用中文。")
