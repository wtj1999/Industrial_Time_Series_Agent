"""Configured read-only online data sources shown in My Data."""

from dataclasses import dataclass


@dataclass(frozen=True)
class OnlineSource:
    name: str
    description: str
    host: str
    port: int
    user: str
    password: str
    database: str


ONLINE_SOURCES: dict[str, OnlineSource] = {
    "jinzhai-phase2": OnlineSource(
        name="金寨二期工厂",
        description="国轩高科在金寨布局的储能电池制造基地，聚焦储能电芯生产与智能化制造。",
        host="10.36.94.17",
        port=19030,
        user="gdmo",
        password="gdmo@123!!",
        database="dwd",
    ),
    "jinzhai-phase3": OnlineSource(
        name="金寨三期工厂",
        description="国轩高科的储能电池制造基地，三期规划建设 10GWh 储能产线。",
        host="10.52.94.75",
        port=19030,
        user="gdmo",
        password="gdmo@123!!",
        database="dwd",
    ),
    "wuhu-phase1": OnlineSource(
        name="芜湖一期工厂",
        description="国轩高科在芜湖布局的新能源电池基地，涵盖动力电池电芯与 PACK 产线。",
        host="10.53.195.56",
        port=19030,
        user="gdmo",
        password="Y@3R!o!@qwq",
        database="dwd",
    ),
    "xinzhan-phase2": OnlineSource(
        name="新站二期工厂",
        description="国轩高科在合肥新站布局的动力电池制造基地，聚焦高性能电芯生产。",
        host="10.34.195.44",
        port=19030,
        user="gdmo",
        password="XZt@2026@gdmo",
        database="dwd",
    ),
}
