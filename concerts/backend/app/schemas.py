from pydantic import BaseModel, Field


class EmotionResponse(BaseModel):
    emocao: str = Field(..., description="Uma das emoções permitidas para o BMO")
    resposta: str = Field(..., description="Texto da resposta em português do Brasil")
