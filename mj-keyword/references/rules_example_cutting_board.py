"""规则文件样例：cutting board（US，2026-10-30，无自家 SKU）。换类目时复制一份到 OUT/rules.py 再按词根表改。

由 scripts/classify.py 读取。可选变量：SKU（适用SKU 列）、PROTECTED_ROOTS（受保护词根）、TYPOS（拼写变体）、
ATTR_PRIORITY（主属性判定顺序）、CHEAP（低价/批量意图写法，不给则取属性里名字带"低价"的值）。
"""
SKU = "通用（未提供SKU）"
PROTECTED_ROOTS = ["knife", "holder", "stand", "tray", "handle", "lip", "groove", "feet", "mat", "cover", "set"]

# 主属性判定顺序（关键词命中多个维度时，取排在前面的维度作为“关键词类型”）
ATTR_PRIORITY = ["材质", "套装组合", "结构工艺", "尺寸规格", "使用场景", "功能卖点", "风格外观", "购买意图"]

ATTRIBUTES = {
    "材质": {
        "钛": ["titanium"],
        "不锈钢/金属": ["stainless", "stainless steel", "steel", "steal", "stainsteel", "stain steel", "metal", "ss", "aluminum",
                     "copper", "acero inoxidable", "inoxidable"],
        "木": ["wood", "wooden", "hardwood", "solid wood", "madera"],
        "木·枫木": ["maple"], "木·胡桃木": ["walnut"], "木·相思木": ["acacia", "acadia"], "木·柚木": ["teak", "teakhaus"],
        "木·橄榄木": ["olive"], "木·樱桃木": ["cherry"], "木·桧木": ["hinoki"], "木·橡木": ["oak"], "木·橡胶木": ["rubberwood"],
        "木·落叶松": ["larch", "larchwood"],
        "竹": ["bamboo", "bambo"],
        "塑料": ["plastic", "hdpe", "poly", "polyethylene", "polypropylene", "pva"],
        "橡胶": ["rubber"], "硅胶": ["silicone"],
        "复合/纸纤维": ["composite", "wood fiber", "paper composite", "paper fiber", "fiber", "richlite", "corian"],
        "玻璃": ["glass", "tempered"], "石材/大理石": ["stone", "marble", "granite", "quartz"], "陶瓷": ["ceramic"],
    },
    "尺寸规格": {
        "大号": ["large", "big", "xl", "xxl", "xxxl", "xlarge", "extra large", "oversized", "huge", "giant"],
        "小号": ["small", "mini", "tiny"], "中号": ["medium"],
        "多尺寸": ["different sizes", "various sizes", "multiple sizes", "variety", "sizes"], "加长": ["long"],
        "具体尺寸": ["re:\\b\\d+(\\.\\d+)?\\s*(x|by)\\s*\\d+", "re:\\b\\d+\\s*(inch|inches|in)\\b"],
        "厚": ["thick", "heavy duty", "heavy"], "薄": ["thin"], "轻便": ["lightweight", "light weight", "light"],
    },
    "结构工艺": {
        "端面": ["end grain"], "边纹": ["edge grain"],
        "肉墩/砧板": ["butcher block", "butchers block", "chopping block", "cutting block", "chop block", "butcher"],
        "双面": ["double sided", "reversible", "2 sided", "two sided"], "实木无胶": ["solid wood", "no glue"],
        "柔性薄片": ["flexible", "mat", "sheet"], "折叠": ["folding", "foldable", "collapsible"], "一次性": ["disposable"],
        "汁槽": ["juice groove", "groove", "juice"], "带边/卡台": ["lip", "counter lip", "countertop", "counter top", "counter"],
        "把手": ["handle", "handles"],
    },
    "功能卖点": {
        "安全·无毒健康": ["non toxic", "nontoxic", "bpa free", "microplastic free", "plastic free", "non plastic",
                 "healthy", "health", "food grade", "safe", "organic", "natural", "pure", "safest", "medical grade"],
        "洗碗机可洗": ["dishwasher safe", "dishwasher", "dish washer"],
        "防滑": ["non slip", "non-slip", "nonslip", "slip", "grip", "grips"],
        "安全·抗菌": ["antibacterial", "antimicrobial", "non porous", "porous", "bacteria"],
        "颜色分类": ["color coded", "colour coded", "colour codes", "colored"], "耐热": ["heat resistant"],
        "护刀": ["knife-friendly", "knife friendly"],
    },
    "套装组合": {
        "套装": ["set", "sets", "pack", "piece", "pcs", "pc", "re:\\bset of \\d+"],
        "含刀": ["knife", "knives", "knife set"], "带支架/收纳": ["with stand", "with holder", "and holder", "and stand",
                                                              "in holder", "in stand", "storage", "with storage"],
        "带托盘/容器": ["tray", "trays", "with container", "containers"],
    },
    "使用场景": {
        "肉类/烧烤": ["meat", "chicken", "raw meat", "steak", "bbq", "carving", "brisket", "turkey", "big game"],
        "蔬果": ["vegetable", "vegetables", "veggies", "veggie", "fruit", "fruits"], "面包": ["bread"],
        "露营/户外": ["camping", "outdoor", "rv", "travel"],
        "商用": ["commercial", "restaurant", "restaurants", "professional", "chef", "nsf", "industrial"],
        "跨界·灶台/水槽盖板": ["sink", "over sink", "stove", "stove top", "stovetop", "cover"],
        "儿童/辅食": ["kids", "kid", "toddler", "children", "baby food"], "跨界·上菜拼盘": ["serving", "charcuterie", "cheese"],
        "无障碍": ["adapted"],
    },
    "风格外观": {
        "装饰/颜值": ["decorative", "decor", "decoration", "decorate", "aesthetic", "cute", "vintage", "unique", "rustic"],
        "棋盘格": ["checkered"], "造型(书本/地图/圆形)": ["round", "book", "books", "library", "shape", "states"],
        "礼品/定制": ["gift", "gifts", "personalized", "engraved", "engrave", "custom", "customized", "housewarming",
                   "with logo", "with name", "initial"],
        "颜色·白": ["white"], "颜色·黑": ["black"], "颜色·棕": ["brown", "dark wood", "dark"], "颜色·粉": ["pink"],
        "颜色·绿": ["green"], "颜色·红": ["red"], "颜色·黄": ["yellow"], "颜色·金": ["gold"], "颜色·紫": ["purple"],
        "颜色·米白": ["cream"], "颜色·灰": ["gray", "grey"], "颜色·透明": ["clear"],
    },
    "购买意图": {
        "低价/批量": ["cheap", "bulk", "under 10", "under 5", "wholesale", "on sale"],
        "评测/口碑": ["best", "top", "rated", "top rated", "high quality", "quality"],
        "产地": ["made in usa", "usa", "american", "japan", "japanese", "korea", "italy", "uk"],
    },
}

# 竞品品牌（整板）：进广告词库「C 竞品测试」，不写进自家文案
BRANDS = ["katori", "tibo", "tivano", "vanotium", "epicurean", "oxo", "john boos", "boos", "teakhaus", "kant",
          "hexclad", "caraway", "auntie rue", "astercook", "katuchef", "gorilla grip", "kitchenaid", "ziruma", "biard",
          "royal craft", "joseph joseph", "zwilling", "victorinox", "charmline", "miu", "asahi", "snowclad",
          "shiny carts", "apex", "made in cutting board", "titan", "sonder", "virginia boys", "greener chef",
          "farberware", "cuisinart", "henckels", "ironwood", "totally bamboo", "freshware", "hasegawa", "boardsmith", "shun",
          "material kitchen", "material cutting board", "mk free", "titanclad", "elihome", "blackstone", "nulas", "thetchry", "hi soft",
          "all clad", "joseph", "guanwei", "yamato", "zamioe", "kitchen aid", "sumzzz", "taima", "kikcoin", "grommet", "keechee",
          "avoletti", "smirly", "pampered chef", "larchwood", "vаnоtіum",
          "our place", "misen"]

# 外语：最多 A2，不写入英文文案
FOREIGN = ["tabla", "tablas", "picar", "cortar", "madera", "cocina", "acero", "inoxidable", "para", "tabua", "carne", "re:[\\u4e00-\\u9fff\\uac00-\\ud7af]"]

# 宽泛/意图混杂：C 低预算探索，西柚反查后再定
BROAD = {"charcuterie boards", "charcuterie board", "serving board", "wood serving board", "bamboo serving board",
         "butcher block", "butchers block", "wood butcher block", "titanium", "board", "wood board", "wood boards",
         "wood boards for food", "wood board for kitchen counter", "food board", "food boards", "cutting block", "chop block",
         "cutting", "chopping", "kitchen board", "cooking board", "wooden board", "wooden boards", "bamboo board", "meat board",
         "butcher board", "stainless steel board", "carving board",
         "chopping block", "block cutting board"}

# 核心同义词（直接叫法）
CORE = {"cutting board", "cutting boards", "chopping board", "chopping boards", "cutting boards for kitchen",
        "cutting board for kitchen", "chopping boards for kitchen", "chopping board for kitchen", "kitchen cutting board",
        "kitchen cutting boards", "cuttingboard", "cutting borad", "kitchen chopping board", "cutting board kitchen",
        "chopping board kitchen", "cutting boards amazon", "food cutting board", "chop board"}
TYPOS = {"cut board", "cutting boatd", "cutting bosrd", "cutter board", "cutting bord", "curring board", "cuting board",
         "cutting boars", "cutting board'", "\ufffccutting board", "cutting. board", "cutting boards'", "\ufffccutting boards"}

# 词组否定：词根本身就代表不是在买菜板（类目级，与自家 SKU 无关）
PHRASE_NEG = [
    ("oil", "护理油/蜡等耗材，不是菜板"), ("wax", "护理油/蜡等耗材，不是菜板"), ("conditioner", "护理油/蜡等耗材，不是菜板"),
    ("butter", "护理油/蜡等耗材，不是菜板"), ("cleaner", "清洁用品，不是菜板"),
    ("board rack", "单独的收纳架/沥水架"), ("boards rack", "单独的收纳架/沥水架"), ("drying rack", "单独的沥水架"),
    ("board organizer", "单独的收纳架"), ("boards organizer", "单独的收纳架"), ("vertical organizer", "单独的收纳架"), ("board holder", "单独的菜板收纳架"),
    ("boards holder", "单独的菜板收纳架"), ("under cabinet", "柜下收纳架配件"), ("hanger", "挂架配件"),
    ("display", "展示架配件"), ("wall mount", "壁挂架配件"),
    ("board feet", "菜板脚垫配件"),
    ("slip mat", "垫在菜板下的防滑垫"), ("grip mat", "垫在菜板下的防滑垫"), ("slip pad", "垫在菜板下的防滑垫"),
    ("mats non slip", "垫在菜板下的防滑垫"),
    ("jig", "木工/DIY 制作菜板"), ("woodworking", "木工/DIY 制作菜板"), ("blanks", "木工/DIY 制作菜板"),
    ("unfinished", "木工/DIY 制作菜板"), ("epoxy", "木工/DIY 制作菜板"),
    ("crafts", "手工/绘画用板，不是厨房用"), ("paint", "手工/绘画用板，不是厨房用"), ("sewing", "缝纫/裁布垫"),
    ("vinyl", "手工刻字材料"), ("board stand", "单独的菜板支架"), ("boards stand", "单独的菜板支架"),
    ("trimmer", "裁纸刀"), ("xacto", "美工刀"), ("varnish", "护理/涂装耗材"),
    ("sanitizer", "消毒器"), ("oiling", "护理工具"), ("scissors", "其他厨房工具"), ("utensils", "其他厨房工具"),
    ("board table", "家具（菜板桌）"),
]
# 精准否定（词根否定会误伤，或只有个别词）
EXACT_NEG = [
    ("cutting board mat", "防滑垫或柔性薄垫，意图混杂", "按搜索词报告启用"),
    ("chopping board mat", "防滑垫或柔性薄垫，意图混杂", "按搜索词报告启用"),
    ("chopping board knife", "可能是在找刀", "按搜索词报告启用"),
    ("cutting board knife", "可能是在找刀", "按搜索词报告启用"),
    ("cutting board craft", "手工/绘画用板，不是厨房用", "建议启用"),
    ("cutting boards craft", "手工/绘画用板，不是厨房用", "建议启用"),
    ("chopping board dish drying", "沥水架配件", "建议启用"),
    ("chopping board bowl", "其他厨房用品", "建议启用"),
    ("chopping board and bowl", "其他厨房用品", "按搜索词报告启用"),
    ("cutting board plates", "餐盘", "建议启用"), ("cutting board plates for eating", "餐盘", "建议启用"),
    ("chopping board table", "家具（菜板桌）", "建议启用"),
    ("chopping board table for kitchen", "家具（菜板桌）", "建议启用"),
    ("pull out cutting board replacement", "橱柜抽拉板替换件", "建议启用"),
    ("cutting board kit", "木工/DIY 制作套件", "建议启用"),
    ("board", "单词泛搜，意图不是菜板", "建议启用"), ("titanium", "单词泛搜（钛金属/钛制品）", "建议启用"),
    ("wood board", "可能是木板材", "按搜索词报告启用"), ("wood boards", "可能是木板材", "按搜索词报告启用"),
    ("cutting board rubber feet", "单独的脚垫配件", "建议启用"), ("chopping board rubber feet", "单独的脚垫配件", "建议启用"),
    ("cutting boards rubber feet", "单独的脚垫配件", "建议启用"), ("cutting board non slip feet", "单独的脚垫配件", "建议启用"),
    ("cutting board legs", "单独的脚垫配件", "按搜索词报告启用"), ("chopping board legs", "单独的脚垫配件", "按搜索词报告启用"),
    ("chopping board scraper", "其他厨房工具", "建议启用"), ("cutting boards laser engraving", "激光雕刻用空白板", "建议启用"),
    ("chopping board and rolling pin", "其他厨房工具", "按搜索词报告启用"),
    ("chopping board organizer", "单独的收纳架", "建议启用"), ("chopping board organizer countertop", "单独的收纳架", "建议启用"),
    ("chopping board organizer under cabinet", "单独的收纳架", "建议启用"), ("cutting board organizer", "单独的收纳架", "建议启用"),
    ("cutting board organizer for cabinet", "单独的收纳架", "建议启用"), ("cutting boards organizer", "单独的收纳架", "建议启用"),
    ("cutting boards organizer for kitchen", "单独的收纳架", "建议启用"),
    ("chopping board bag", "收纳袋", "建议启用"), ("chopping board template", "木工模板", "建议启用"),
    ("chopping board drainer", "沥水配件", "建议启用"), ("cutting board accessories", "配件", "建议启用"),
    ("chopping board riser", "垫高配件", "建议启用"), ("chopping board golf", "无关", "建议启用"),
    ("cutting board vertical holder", "单独的菜板收纳架", "建议启用"), ("cutting boards hanging", "挂架", "按搜索词报告启用"),
    ("cutting boards to hang", "挂架或装饰挂板", "按搜索词报告启用"), ("chopping board guide", "无关", "按搜索词报告启用"), ("cutting boards kits", "木工/DIY 制作套件", "建议启用"),
    ("cutting board wood kit", "木工/DIY 制作套件", "建议启用"),
    ("cutting board storage", "收纳配件", "按搜索词报告启用"), ("cutting boards storage", "收纳配件", "按搜索词报告启用"),
    ("chopping board storage", "收纳配件", "按搜索词报告启用"),
]
