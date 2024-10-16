import pydantic


class InternetExchangeMemberMetaData(pydantic.BaseModel):

    case_number: list[str | int] | None = None

class InternetExchangeConfig(pydantic.BaseModel):

    port_sizes: list[int] = pydantic.Field(default_factory=list)