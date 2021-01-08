import os
import json
import re
import zipfile

all_input_recipes = {}
all_output_recipes = {}
packing_list = {}
unpacking_list = {}

def gather_recipes_dir(input_dir, modid, prefix=None):
    print('gather', input_dir)
    if prefix is None: prefix = modid + ':'
    for root, dirs, files in os.walk(input_dir):
       for name in files:
           if not name.endswith('.json'): continue
           fullpath = os.path.join(root, name)
           recipe_in = json.load(open(fullpath))
           recipe_in['_modid'] = modid
           if not fullpath.startswith(input_dir):
               raise Exception('unexpected path name')
           name = fullpath.replace(input_dir, '', 1).replace('\\', '/').replace('.json', '')
           while name.startswith('/'): name = name[1:]
           name = prefix+name
           recipe_in['_name'] = name
           all_input_recipes[name] = recipe_in

all_input_tags = {}

def gather_recipes_jar(input_jar):
    print('gather', input_jar)
    zf = zipfile.ZipFile(input_jar)
    for info in zf.infolist():
        m = re.match('data/([a-z_]+)/tags/items/(.+).json', info.filename)
        if m:
            data = json.load(zf.open(info))
            tag_name = m.group(1) + ':' + m.group(2)
            if data['replace'] or tag_name not in all_input_tags:
                all_input_tags[tag_name] = data['values']
            else:
                all_input_tags[tag_name].extend(data['values'])
            continue
                
        m = re.match('data/([a-z_]+)/recipes/(.+).json', info.filename)
        if m:
            modid = m.group(1)
            recipe_name = m.group(2)
            key = f'{modid}:{recipe_name}'
            recipe_in = json.load(zf.open(info))
            recipe_in['_modid'] = modid
            all_input_recipes[key] = recipe_in
            recipe_in['_name'] = key
            continue

pams_grinder = {'tag': 'forge:tool_grinder'}

def apply_mod_condition(recipe_in, recipe_out):
    modid = recipe_in.get('_modid')
    if 'conditions' in recipe_in:
        conditions = recipe_in['conditions'].copy()
    else:
        conditions = []
    if modid and modid not in ('minecraft', 'forge'):
        conditions.append({"type": "forge:mod_loaded", "modid": recipe_in['_modid']})
    if conditions:
        recipe_out['conditions'] = conditions

def process_pams_grinder(name, recipe_in):
    if recipe_in['type'] != 'minecraft:crafting_shapeless':
        return
    ingredients = recipe_in['ingredients']
    if len(ingredients) != 2 or pams_grinder not in ingredients:
        return
    ingredient, = [i for i in ingredients if i != pams_grinder]
    recipe_out = {
            "type": "thermal:pulverizer",
            "ingredient": ingredient,
            "result": [recipe_in['result']],
            "energy": 400}
    apply_mod_condition(recipe_in, recipe_out)
    tmp = recipe_in['_modid'].replace('pam', '')
    tmp2 = re.sub('.*[:/]', '', name)
    all_output_recipes[f'thermal:compat/pam/{tmp}/{tmp2}'] = recipe_out

def pattern_is_2x2(pattern):
    line = pattern[0]
    return len(pattern) == 2 and len(line) == 2 \
            and line[0] == line[1] \
            and line == pattern[1]

def pattern_is_3x3(pattern):
    line = pattern[0]
    return len(pattern) == 3 and len(line) == 3 \
            and line[0] == line[1] == line[2] \
            and line == pattern[1] == pattern[2]

def process_packing(name, recipe_in):
    if recipe_in['type'] != 'minecraft:crafting_shaped':
        return
    pattern = recipe_in['pattern']
    if pattern_is_2x2(pattern):
        count = 4
        die = {"item": "thermal:press_packing_2x2_die"}
    elif pattern_is_3x3(pattern):
        count = 9
        die = {"item": "thermal:press_packing_3x3_die"}
    else:
        return
    result = recipe_in['result']
    if result.get('count', 1) != 1:
        return
    ingredient, = recipe_in['key'].values()
    has_unpack = False
    if 'item' in ingredient:
        has_unpack = result['item'] in unpacking_list
        if has_unpack:
            unpack_recipe = unpacking_list[result['item']]
            unpack_name = unpack_recipe['_name']
        ingstr = ingredient['item']
        unpack_item = result['item']
    elif 'tag' in ingredient:
        unpack_item = unpacking_list.get(result['item'])
        if unpack_item:
            unpack_name = unpack_item['_name']
            unpack_item = unpack_item['result']['item']
        else:
            unpack_name = name + '_unpack'
        tag = ingredient['tag']
        ingstr = 'TAG:'+tag
        if tag not in all_input_tags:
            print(f'missing tag data {tag} for packing candidate {name}')
            return
        taglst = all_input_tags[tag]
        has_unpack = unpack_item in taglst
    if not has_unpack:
        print(f'packing maybe: {name},{count},{ingstr},{result["item"]}')
        return
    ingredient = ingredient.copy()
    ingredient['count'] = count
    packing_recipe = {
            "type": "thermal:press",
            "input": [ingredient, die],
            "result": result,
            "energy": 400
            }
    apply_mod_condition(recipe_in, packing_recipe)
    unpacking_recipe = {
            "type": "thermal:press",
            "input": [result, {"item": "thermal:press_unpacking_die"}],
            "result": {"item": unpack_item, "count": count},
            "energy": 400,
            }
    modid = recipe_in.get('_modid', 'unknown')
    tmp2 = re.sub('.*[:/]', '', name)
    tmp3 = re.sub('.*[:/]', '', unpack_name)
    apply_mod_condition(recipe_in, unpacking_recipe)
    all_output_recipes[f'thermal:compat/{modid}/{tmp2}'] = packing_recipe
    all_output_recipes[f'thermal:compat/{modid}/{tmp3}'] = unpacking_recipe
    if 'allthemod' in name:
        print(packing_recipe)
        print(unpacking_recipe)
            

def preprocess_unpacking(name, recipe_in):
    if recipe_in['type'] != 'minecraft:crafting_shapeless': return
    if len(recipe_in['ingredients']) != 1: return
    count = recipe_in['result'].get('count', 1)
    if count not in (4, 9): return
    ingredient = recipe_in['ingredients'][0]
    if 'item' not in ingredient:
        print(f'ignoring tag ingredient {ingredient} in unpacking recipe {name}')
        return
    unpacking_list[ingredient['item']] = recipe_in

def print_packing():
    for ((item, die), result) in packing_list.items():
        result_item = result['item']
        if result_item in unpacking_list \
            and unpacking_list[result_item]['item'] == item:
                print('definite packing recipe', item, die, result_item)
        else:
            print('uncertain packing recipe', item, die, result_item)

gather_recipes_dir('../repos/phc2foodcore/src/main/resources/data/pamhc2foodcore/recipes', 'pamhc2foodcore')
gather_recipes_dir('../repos/phc2foodextended/src/main/resources/data/pamhc2foodextended/recipes', 'pamhc2foodextended')
#gather_recipes_dir('../vanilla-recipes', 'minecraft')
#gather_recipes_jar('../Mods/Quark-r2.4-290.jar')
#gather_recipes_jar("../Mods/buzzier_bees-1.16.4-3.0.0.jar")
#gather_recipes_jar("../Mods/ResourcefulBees1.16.3-1.16.4-0.5.8b.jar")
gather_recipes_jar("../Mods/productivebees-1.16.4-0.5.2.8.jar")

for name, recipe in all_input_recipes.items():
    preprocess_unpacking(name, recipe)
for name, recipe in all_input_recipes.items():
    process_pams_grinder(name, recipe)
    process_packing(name, recipe)
for name, recipe in all_output_recipes.items():
    print(name)
    modid, _, name = name.partition(':')
    filename_out = f'data/{modid}/recipes/{name}.json'
    os.makedirs(os.path.dirname(filename_out), exist_ok=True)
    json.dump(recipe, open(filename_out, 'w'), indent=4)
print_packing()

#os.makedirs(output_dir, exist_ok=True)
