import json
from pydantic import BaseModel


class PricingModel(BaseModel):
    "pricing model output"

    InputToken: int = 0
    InputChar: int = 0

    OutputToken: int = 0
    OutputChar: int = 0
    ImageUsage: int = 0

    def __add__(self, other):
        if isinstance(other, self.__class__):
            return PricingModel(
                InputToken=self.InputToken + other.InputToken,
                InputChar=self.InputChar + other.InputChar,

                OutputToken=self.OutputToken + other.OutputToken,
                OutputChar=self.OutputChar + other.OutputChar,

                ImageUsage=self.ImageUsage + other.ImageUsage,
            )
        return self

    @property
    def InputPrice(self) -> float:
        if self.InputToken > 128000:
            # $3.50 / 1 million tokens
            price = self.InputToken * 3.50 / 1_000_000
        else:
            # $7.00 / 1 million tokens
            price = self.InputToken * 7.00 / 1_000_000
        return price

    @property
    def OutputPrice(self) -> float:
        if self.OutputToken > 128000:
            # $10.50 / 1 million tokens
            price = self.OutputToken * 3.50 / 1_000_000
        else:
            # $7.00 / 1 million tokens
            price = self.OutputToken * 7.00 / 1_000_000

        return price

    @property
    def ImagePrice(self) -> float:
        # $0.020 / image
        return self.ImageUsage * 0.020

    @property
    def TotalPrice(self) -> float:
        return self.InputPrice + self.OutputPrice + self.ImagePrice

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data.update({
            'InputPrice': self.InputPrice,
            'OutputPrice': self.OutputPrice,
            'ImagePrice': self.ImagePrice,
            'TotalPrice': self.TotalPrice,
        })
        return data

    def __repr__(self) -> str:
        return json.dumps(self.model_dump)
