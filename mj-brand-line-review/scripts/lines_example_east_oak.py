import json,collections
LINE={
 "Pellet Grills & Smoker Units":"户外电熏炉",
 "Electric Lunch Boxes & Food Warmers":"电热饭盒",
 "Pop-Up Canopies & Screen Houses":"帐篷遮阳","Clear Bubble Tents & Sports Pods":"帐篷遮阳","Vehicle Tents":"帐篷遮阳","Sun Shade Sails & Shade Cloth":"帐篷遮阳","Patio Umbrellas":"帐篷遮阳",
 "Outdoor Storage Boxes & Package Del":"庭院储物","Trash Cans & Wastebaskets":"庭院储物",
 "Patio Furniture Sets & Seating":"户外家具","Outdoor Dining Tables & Sets":"户外家具","Porch Swings & Gliders":"户外家具","Accent Chairs & Chaise Lounges":"户外家具","Oversized & Heavy Duty Camping Chai":"户外家具",
 "Patio Heaters":"庭院取暖器","Space, Outdoor & Vehicular Heaters":"庭院取暖器",
 "Fire Pits":"庭院火炉","Outdoor Fire Pits & Accessories":"庭院火炉","Outdoor Fire Pit Covers & Spark Scr":"庭院火炉",
}
def line_of(i):
    c=i.get('internalCategoryTree') or {}
    path=[p['categoryName']['original'] for p in c.get('path',[])]
    k=path[-2] if len(path)>=2 else '?'
    for kk,v in LINE.items():
        if k.startswith(kk[:30]): return v
    return "其他"
def mrev(i):
    return {t['localDate'][:7]:float(t['salesRevenue']['value'] or 0) for t in i['asinsTrends']['trends']}
def munits(i):
    return {t['localDate'][:7]:int(t['sales']['value'] or 0) for t in i['asinsTrends']['trends']}
