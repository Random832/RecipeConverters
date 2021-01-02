import os
import json


grinder = {'tag': 'forge:tool_grinder'}

def convert_recipes(input_dir, output_dir, modid):
    os.makedirs(output_dir, exist_ok=True)
    for fn in os.scandir(input_dir):
        if os.path.splitext(fn)[1] != '.json': continue
        recipe_in = json.load(open(fn))
        if recipe_in['type'] != 'minecraft:crafting_shapeless': continue
        ingredients = recipe_in['ingredients']
        if len(ingredients) != 2: continue
        if grinder not in ingredients: continue
        ingredients.remove(grinder)
        recipe_out = {
                "type": "thermal:pulverizer",
                "ingredient": ingredients[0],
                "result": [recipe_in['result']],
                "energy_mod": 0.5,
                "conditions": [{"type": "forge:mod_loaded", "modid": modid}]}
        print(fn.name)
        json.dump(recipe_out, open(output_dir + '/' + fn.name, 'w'), indent=4)

convert_recipes(
        '../repos/phc2foodcore/src/main/resources/data/pamhc2foodcore/recipes',
        'recipes/pams', 'pamhc2foodcore')
convert_recipes(
        '../repos/phc2foodextended/src/main/resources/data/pamhc2foodextended/recipes',
        'recipes/pams', 'pamhc2foodextended')
