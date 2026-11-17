"""Generates a synthetic grocery catalog (about 250 products) in data/products.json.

All brands and products are invented. Nothing here is real retailer data.

    python data/generate_catalog.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

random.seed(42)

BRANDS = ["Harvest Lane", "Golden Field", "Pure Pantry", "Green Valley", "Ocean Bay",
          "Sunny Acres", "Morning Mill", "Nonna's Table", "Simply Fresh", "Peak Nutrition"]
STORES = [f"store-{n}" for n in range(1001, 1011)]
AISLES = {
    "pasta": "Aisle 7 - Pasta & Sauces", "sauces": "Aisle 7 - Pasta & Sauces",
    "rice & grains": "Aisle 8 - Rice & Grains", "dairy": "Aisle 2 - Dairy",
    "bakery": "Aisle 1 - Bakery", "snacks": "Aisle 10 - Snacks",
    "produce": "Produce", "breakfast": "Aisle 5 - Breakfast",
    "beverages": "Aisle 12 - Beverages", "frozen": "Aisle 14 - Frozen",
    "meat & seafood": "Meat & Seafood", "plant protein": "Aisle 3 - Plant Protein",
}

# (category, item, size, price range, [(variant, extra tags, description)])
BASES = [
    ("pasta", "Penne", "16 oz", (1.2, 2.5), [
        ("", [], "Classic durum wheat penne that holds chunky sauces well. Ready in 11 minutes."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free penne made from brown rice and corn, with a firm bite that doesn't go mushy."),
        ("Chickpea", ["gluten-free", "vegan", "high-protein"], "Penne made from chickpeas, with 20 g of protein per serving and no gluten."),
        ("Whole Wheat", ["vegan"], "Whole wheat penne with extra fiber for a heartier weeknight dinner."),
        ("Organic", ["organic", "vegan"], "Organic durum wheat penne, slow-dried in bronze dies."),
    ]),
    ("pasta", "Spaghetti", "16 oz", (1.0, 2.4), [
        ("", [], "Long, thin pasta for marinara, meatballs or garlic and olive oil."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free spaghetti made from corn and rice. Great for family pasta night."),
        ("Lentil", ["gluten-free", "vegan", "high-protein"], "Red lentil spaghetti, high in protein and naturally gluten-free."),
        ("Whole Wheat", ["vegan"], "Whole grain spaghetti with a nutty flavor."),
    ]),
    ("pasta", "Fusilli", "16 oz", (1.3, 2.6), [
        ("", [], "Spiral pasta that catches pesto and creamy sauces. Good for pasta salad."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free fusilli made with quinoa and rice."),
        ("Organic", ["organic", "vegan"], "Organic fusilli made from Italian durum wheat."),
    ]),
    ("pasta", "Macaroni & Cheese", "6 oz", (1.0, 3.5), [
        ("", ["vegetarian"], "Creamy boxed mac and cheese, ready in 10 minutes. A kid favorite."),
        ("Gluten-Free", ["gluten-free", "vegetarian"], "Gluten-free rice pasta with a real cheddar cheese sauce."),
        ("Vegan", ["vegan", "dairy-free"], "Dairy-free mac and cheese with a cashew-based cheese sauce."),
    ]),
    ("pasta", "Lasagna Sheets", "9 oz", (2.5, 4.5), [
        ("No-Boil", [], "Oven-ready lasagna sheets, no boiling needed."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free oven-ready lasagna sheets made from rice flour."),
    ]),
    ("sauces", "Marinara Sauce", "24 oz", (2.5, 6.5), [
        ("", ["vegan"], "Slow-simmered tomato sauce with garlic, basil and olive oil."),
        ("Low Sodium", ["vegan", "low-sodium"], "Marinara with 50% less sodium, still full of tomato flavor."),
        ("Organic", ["organic", "vegan"], "Organic tomatoes, onions and herbs. No added sugar."),
    ]),
    ("sauces", "Alfredo Sauce", "15 oz", (3.0, 5.5), [
        ("", ["vegetarian"], "Rich, creamy parmesan sauce for fettuccine and chicken."),
        ("Dairy-Free", ["vegan", "dairy-free"], "Creamy plant-based alfredo made from cashews."),
    ]),
    ("sauces", "Basil Pesto", "6 oz", (3.5, 6.0), [
        ("", ["vegetarian"], "Fresh basil, pine nuts, parmesan and olive oil."),
        ("Vegan", ["vegan", "dairy-free"], "Basil pesto without cheese, made with sunflower seeds. Nut-free.")]),
    ("sauces", "Arrabbiata Sauce", "24 oz", (3.0, 6.0), [
        ("", ["vegan"], "Spicy tomato sauce with red chili flakes and garlic.")]),
    ("rice & grains", "Brown Rice", "32 oz", (2.0, 4.5), [
        ("", ["gluten-free", "vegan"], "Long grain brown rice, a whole grain side for any meal."),
        ("Microwave", ["gluten-free", "vegan"], "Fully cooked brown rice pouch, ready in 90 seconds."),
    ]),
    ("rice & grains", "Jasmine Rice", "32 oz", (2.5, 5.5), [
        ("", ["gluten-free", "vegan"], "Fragrant Thai jasmine rice, soft and slightly sticky."),
        ("Organic", ["gluten-free", "vegan", "organic"], "Organic jasmine rice from Thailand.")]),
    ("rice & grains", "Quinoa", "16 oz", (3.5, 6.5), [
        ("", ["gluten-free", "vegan", "high-protein"], "White quinoa, a complete plant protein that cooks in 15 minutes."),
        ("Tri-Color", ["gluten-free", "vegan", "high-protein", "organic"], "Organic red, white and black quinoa blend.")]),
    ("dairy", "Milk", "1 gal", (3.0, 5.5), [
        ("Whole", ["vegetarian"], "Fresh whole milk from local farms."),
        ("2% Reduced Fat", ["vegetarian"], "2% milk with vitamins A and D."),
        ("Lactose-Free", ["vegetarian"], "Real milk without the lactose, easy to digest."),
        ("Organic Whole", ["vegetarian", "organic"], "Organic whole milk from grass-fed cows.")]),
    ("dairy", "Oat Milk", "64 oz", (3.5, 5.5), [
        ("", ["vegan", "dairy-free"], "Creamy oat milk that froths well for lattes."),
        ("Unsweetened", ["vegan", "dairy-free", "sugar-free"], "Oat milk with no added sugar.")]),
    ("dairy", "Almond Milk", "64 oz", (3.0, 4.8), [
        ("Unsweetened", ["vegan", "dairy-free", "keto", "sugar-free"], "Unsweetened almond milk, 30 calories per cup. Contains tree nuts.")]),
    ("dairy", "Greek Yogurt", "32 oz", (4.0, 7.0), [
        ("Plain", ["vegetarian", "high-protein", "gluten-free"], "Thick plain Greek yogurt with 18 g of protein per serving."),
        ("Vanilla", ["vegetarian", "high-protein", "gluten-free"], "Lightly sweet vanilla Greek yogurt."),
        ("Coconut", ["vegan", "dairy-free"], "Dairy-free coconut yogurt with live cultures.")]),
    ("dairy", "Cheddar Cheese", "8 oz", (2.5, 5.5), [
        ("Sharp", ["vegetarian", "gluten-free", "keto"], "Aged sharp cheddar block, great for snacking or melting."),
        ("Shredded Mild", ["vegetarian", "gluten-free", "keto"], "Shredded mild cheddar for tacos and casseroles."),
        ("Plant-Based", ["vegan", "dairy-free"], "Dairy-free cheddar-style shreds that melt.")]),
    ("dairy", "Butter", "16 oz", (3.5, 6.5), [
        ("Salted", ["vegetarian", "gluten-free", "keto"], "Sweet cream salted butter."),
        ("Plant Butter", ["vegan", "dairy-free"], "Plant-based butter made from olive and avocado oil.")]),
    ("bakery", "Sandwich Bread", "20 oz", (2.0, 5.5), [
        ("White", ["vegetarian"], "Soft white sandwich bread."),
        ("Whole Wheat", ["vegan"], "100% whole wheat bread with no high-fructose corn syrup."),
        ("Gluten-Free", ["gluten-free", "vegetarian"], "Gluten-free sandwich bread that doesn't crumble. Keep frozen for freshness."),
        ("Keto", ["keto", "vegetarian"], "Low-carb bread with 1 g net carbs per slice.")]),
    ("bakery", "Sourdough Loaf", "24 oz", (4.0, 7.0), [
        ("", ["vegan"], "Crusty sourdough baked fresh in store every morning.")]),
    ("bakery", "Bagels", "6 ct", (3.0, 5.0), [
        ("Everything", ["vegan"], "Chewy everything bagels with sesame, poppy seeds and garlic."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free plain bagels, best toasted.")]),
    ("bakery", "Tortillas", "10 ct", (2.0, 4.5), [
        ("Flour", ["vegan"], "Soft flour tortillas for burritos and wraps."),
        ("Corn", ["gluten-free", "vegan"], "Authentic corn tortillas for street tacos."),
        ("Low Carb", ["keto", "vegan"], "Low-carb high-fiber tortillas.")]),
    ("snacks", "Potato Chips", "8 oz", (2.5, 4.5), [
        ("Sea Salt", ["gluten-free", "vegan"], "Kettle-cooked potato chips with sea salt."),
        ("Baked", ["gluten-free", "vegan", "low-sodium"], "Baked chips with 65% less fat.")]),
    ("snacks", "Tortilla Chips", "11 oz", (2.5, 4.5), [
        ("", ["gluten-free", "vegan"], "Crunchy white corn tortilla chips for salsa and guacamole."),
        ("Blue Corn", ["gluten-free", "vegan", "organic"], "Organic blue corn tortilla chips.")]),
    ("snacks", "Pretzels", "16 oz", (2.0, 4.0), [
        ("", ["vegan"], "Classic salted mini pretzels."),
        ("Gluten-Free", ["gluten-free", "vegan"], "Gluten-free pretzel twists made from potato and corn.")]),
    ("snacks", "Trail Mix", "12 oz", (4.0, 7.5), [
        ("", ["vegan", "gluten-free"], "Peanuts, almonds, raisins and chocolate pieces. Energy for hikes."),
        ("Nut-Free", ["vegan", "nut-free"], "Seeds, dried fruit and pretzels. Safe for school lunches.")]),
    ("snacks", "Granola Bars", "6 ct", (2.5, 5.0), [
        ("Chocolate Chip", ["vegetarian"], "Chewy granola bars with chocolate chips."),
        ("Protein", ["vegetarian", "high-protein", "gluten-free"], "12 g protein bars made with peanut butter and oats."),
        ("Nut-Free", ["vegan", "nut-free"], "School-safe oat bars made in a nut-free facility.")]),
    ("snacks", "Popcorn", "6 ct", (2.5, 4.5), [
        ("Microwave Butter", ["gluten-free", "vegetarian"], "Movie-theater butter microwave popcorn."),
        ("Lightly Salted", ["gluten-free", "vegan", "low-sodium"], "Air-popped popcorn with a light sprinkle of salt.")]),
    ("produce", "Bananas", "per lb", (0.5, 0.8), [("", ["gluten-free", "vegan"], "Ripe yellow bananas, great for smoothies and lunch boxes."),
                                                  ("Organic", ["gluten-free", "vegan", "organic"], "Organic Fair Trade bananas.")]),
    ("produce", "Avocados", "each", (1.0, 2.0), [("Hass", ["gluten-free", "vegan", "keto"], "Creamy Hass avocados for guacamole and toast.")]),
    ("produce", "Baby Spinach", "5 oz", (2.5, 4.5), [("", ["gluten-free", "vegan"], "Triple-washed baby spinach for salads and smoothies."),
                                                     ("Organic", ["gluten-free", "vegan", "organic"], "Organic baby spinach.")]),
    ("produce", "Strawberries", "16 oz", (2.5, 5.0), [("", ["gluten-free", "vegan"], "Sweet, juicy strawberries.")]),
    ("produce", "Honeycrisp Apples", "3 lb bag", (4.0, 7.0), [("", ["gluten-free", "vegan"], "Crisp, sweet apples for snacking.")]),
    ("produce", "Baby Carrots", "16 oz", (1.2, 2.5), [("", ["gluten-free", "vegan"], "Peeled baby carrots, ready to dip.")]),
    ("breakfast", "Rolled Oats", "42 oz", (3.0, 6.0), [("Old Fashioned", ["vegan"], "Whole grain rolled oats for oatmeal and baking."),
                                                       ("Gluten-Free", ["gluten-free", "vegan"], "Certified gluten-free oats, processed in a dedicated facility.")]),
    ("breakfast", "Granola", "12 oz", (3.5, 6.0), [("Honey Almond", ["vegetarian"], "Crunchy honey almond granola clusters."),
                                                   ("Keto", ["keto", "gluten-free", "sugar-free"], "Grain-free granola made from nuts and seeds, no added sugar.")]),
    ("breakfast", "Cereal", "12 oz", (3.0, 5.5), [("Frosted Flakes", ["vegetarian"], "Sweetened corn flakes kids love."),
                                                  ("High Fiber", ["vegan"], "Bran cereal with 10 g of fiber per serving."),
                                                  ("Gluten-Free Rice Crisps", ["gluten-free", "vegan"], "Crispy rice cereal, gluten-free.")]),
    ("breakfast", "Pancake Mix", "32 oz", (2.5, 5.5), [("Buttermilk", ["vegetarian"], "Fluffy buttermilk pancakes, just add water."),
                                                       ("Gluten-Free", ["gluten-free", "vegetarian"], "Gluten-free pancake and waffle mix."),
                                                       ("Protein", ["high-protein", "vegetarian"], "Pancake mix with 15 g of protein per serving.")]),
    ("breakfast", "Peanut Butter", "16 oz", (2.5, 5.0), [("Creamy", ["vegan", "gluten-free"], "Smooth peanut butter. Contains peanuts."),
                                                         ("Natural Crunchy", ["vegan", "gluten-free", "sugar-free"], "Just peanuts and salt, no added sugar.")]),
    ("beverages", "Ground Coffee", "12 oz", (6.0, 11.0), [("Medium Roast", ["vegan", "gluten-free"], "Smooth medium roast with chocolate notes."),
                                                          ("Decaf", ["vegan", "gluten-free"], "Swiss Water decaf, full flavor without the caffeine."),
                                                          ("Organic Dark Roast", ["vegan", "gluten-free", "organic"], "Bold organic dark roast.")]),
    ("beverages", "Green Tea", "20 ct", (2.5, 5.0), [("", ["vegan", "gluten-free", "sugar-free"], "Smooth green tea bags.")]),
    ("beverages", "Sparkling Water", "12 pk", (3.5, 6.0), [("Lime", ["vegan", "gluten-free", "sugar-free"], "Zero-calorie lime sparkling water."),
                                                           ("Berry", ["vegan", "gluten-free", "sugar-free"], "Berry sparkling water, no sweeteners.")]),
    ("beverages", "Orange Juice", "52 oz", (3.0, 5.5), [("Not From Concentrate", ["vegan", "gluten-free"], "100% orange juice, no pulp.")]),
    ("beverages", "Kombucha", "16 oz", (2.5, 4.0), [("Ginger", ["vegan", "gluten-free", "organic"], "Organic ginger kombucha with live probiotics.")]),
    ("frozen", "Pizza", "each", (4.0, 9.0), [("Pepperoni", [], "Rising crust pepperoni pizza."),
                                             ("Gluten-Free Margherita", ["gluten-free", "vegetarian"], "Margherita pizza on a cauliflower and rice crust, gluten-free."),
                                             ("Vegan Veggie", ["vegan", "dairy-free"], "Roasted vegetable pizza with dairy-free cheese.")]),
    ("frozen", "Ice Cream", "1.5 qt", (3.5, 6.5), [("Vanilla Bean", ["vegetarian", "gluten-free"], "Creamy vanilla bean ice cream."),
                                                   ("Oat Milk Chocolate", ["vegan", "dairy-free"], "Dairy-free chocolate frozen dessert made with oat milk."),
                                                   ("Keto Mint Chip", ["keto", "sugar-free", "vegetarian"], "Low-carb mint chip ice cream, no added sugar.")]),
    ("frozen", "Mixed Vegetables", "16 oz", (1.5, 3.0), [("", ["gluten-free", "vegan"], "Frozen corn, peas, carrots and green beans.")]),
    ("frozen", "Veggie Burgers", "4 ct", (4.0, 7.0), [("", ["vegan", "high-protein"], "Plant-based burgers that grill like beef."),
                                                      ("Black Bean", ["vegan", "gluten-free"], "Black bean burgers with corn and peppers.")]),
    ("meat & seafood", "Chicken Breast", "per lb", (3.0, 6.0), [("Boneless Skinless", ["gluten-free", "high-protein", "keto"], "Fresh boneless chicken breasts, no added hormones."),
                                                                ("Organic", ["gluten-free", "high-protein", "keto", "organic"], "Organic free-range chicken breasts.")]),
    ("meat & seafood", "Ground Beef", "per lb", (4.0, 7.0), [("85% Lean", ["gluten-free", "high-protein", "keto"], "Fresh ground beef for burgers and tacos."),
                                                             ("Grass-Fed", ["gluten-free", "high-protein", "keto", "organic"], "100% grass-fed ground beef.")]),
    ("meat & seafood", "Salmon Fillet", "per lb", (8.0, 13.0), [("Atlantic", ["gluten-free", "high-protein", "keto"], "Fresh Atlantic salmon, rich in omega-3."),
                                                                ("Wild Sockeye", ["gluten-free", "high-protein", "keto"], "Wild-caught sockeye salmon.")]),
    ("meat & seafood", "Shrimp", "16 oz", (7.0, 12.0), [("Frozen Peeled", ["gluten-free", "high-protein", "keto"], "Peeled and deveined frozen shrimp, quick to cook.")]),
    ("plant protein", "Tofu", "14 oz", (1.8, 3.5), [("Extra Firm", ["vegan", "gluten-free", "high-protein"], "Extra firm tofu for stir-fry and baking."),
                                                    ("Organic Silken", ["vegan", "gluten-free", "organic"], "Silken tofu for smoothies and desserts.")]),
    ("plant protein", "Tempeh", "8 oz", (2.5, 4.0), [("", ["vegan", "high-protein"], "Fermented soybean tempeh with a nutty taste.")]),
    ("plant protein", "Chickpeas", "15 oz", (0.9, 1.8), [("", ["vegan", "gluten-free", "high-protein", "low-sodium"], "No-salt-added canned chickpeas for hummus and curries.")]),
]


def main():
    products, n = [], 1
    for category, item, size, (lo, hi), variants in BASES:
        for variant, tags, desc in variants:
            for brand in random.sample(BRANDS, k=random.choice([1, 2, 2, 3])):
                name = f"{brand} {variant + ' ' if variant else ''}{item}"
                price = round(random.uniform(lo, hi) * (1.15 if "organic" in tags else 1.0), 2)
                products.append({
                    "sku": f"SKU-{n:05d}",
                    "name": name,
                    "brand": brand,
                    "category": category,
                    "aisle": AISLES[category],
                    "description": desc,
                    "diet_tags": sorted(set(tags)),
                    "price": price,
                    "size": size,
                    "rating": round(random.uniform(3.4, 4.9), 1),
                    "popularity": random.randint(10, 1000),
                    "in_stock_stores": sorted(random.sample(STORES, k=random.randint(4, 10))),
                })
                n += 1
    out = Path(__file__).with_name("products.json")
    out.write_text(json.dumps(products, indent=1))
    print(f"Wrote {len(products)} products to {out}")


if __name__ == "__main__":
    main()
