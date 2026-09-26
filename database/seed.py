"""
Seed the plants table with a curated dataset for the demo.

Framework Section 8 rule: seed a curated dataset first, don't block the
MVP on finding a perfect external plant API.

Run from repo root:
    python database/seed.py
Safe to re-run -- it clears and re-inserts every time (fine pre-demo;
don't run this against a database that already has real My Garden data
you want to keep, since garden entries reference plant ids by number).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.db import get_db, init_db

PLANTS = [
    dict(common_name="Snake Plant", scientific_name="Dracaena trifasciata",
         category="Succulent", water="Low - every 2-3 weeks",
         light="Low to bright indirect", soil="Well-draining cactus mix",
         temperature="60-85F", difficulty="Easy",
         summary="Nearly indestructible; tolerates neglect and low light.",
         image_url="/static/assets/plants/snake_plant.jpg"),
    dict(common_name="Pothos", scientific_name="Epipremnum aureum",
         category="Vine", water="Medium - when top inch is dry",
         light="Low to bright indirect", soil="Standard potting mix",
         temperature="65-85F", difficulty="Easy",
         summary="Fast-growing trailing vine, great for beginners and hanging pots.",
         image_url="/static/assets/plants/pothos.jpg"),
    dict(common_name="Monstera Deliciosa", scientific_name="Monstera deliciosa",
         category="Tropical", water="Medium - weekly",
         light="Bright indirect", soil="Chunky aroid mix",
         temperature="65-85F", difficulty="Easy",
         summary="Iconic split-leaf tropical; likes to climb a moss pole.",
         image_url="/static/assets/plants/monstera.jpg"),
    dict(common_name="ZZ Plant", scientific_name="Zamioculcas zamiifolia",
         category="Succulent", water="Low - every 3-4 weeks",
         light="Low to bright indirect", soil="Well-draining potting mix",
         temperature="65-90F", difficulty="Easy",
         summary="Glossy, drought-tolerant, thrives on benign neglect.",
         image_url="/static/assets/plants/zz_plant.jpg"),
    dict(common_name="Fiddle Leaf Fig", scientific_name="Ficus lyrata",
         category="Tree", water="Medium - when top 2 inches dry",
         light="Bright indirect", soil="Well-draining potting mix",
         temperature="65-75F", difficulty="Hard",
         summary="Dramatic large leaves; sensitive to drafts and overwatering.",
         image_url="/static/assets/plants/fiddle_leaf_fig.jpg"),
    dict(common_name="Aloe Vera", scientific_name="Aloe barbadensis miller",
         category="Succulent", water="Low - every 2-3 weeks",
         light="Bright direct to indirect", soil="Cactus/succulent mix",
         temperature="55-80F", difficulty="Easy",
         summary="Medicinal gel-filled leaves; hates soggy soil.",
         image_url="/static/assets/plants/aloe_vera.jpg"),
    dict(common_name="Peace Lily", scientific_name="Spathiphyllum wallisii",
         category="Tropical", water="Medium - keep lightly moist",
         light="Low to medium indirect", soil="Standard potting mix",
         temperature="65-80F", difficulty="Easy",
         summary="Droops dramatically when thirsty, then perks right back up.",
         image_url="/static/assets/plants/peace_lily.jpg"),
    dict(common_name="Fern (Boston)", scientific_name="Nephrolepis exaltata",
         category="Fern", water="High - keep consistently moist",
         light="Medium indirect", soil="Moisture-retentive potting mix",
         temperature="65-75F", difficulty="Medium",
         summary="Loves humidity; crisps up fast in dry indoor air.",
         image_url="/static/assets/plants/boston_fern.jpg"),
    dict(common_name="Jade Plant", scientific_name="Crassula ovata",
         category="Succulent", water="Low - every 2-3 weeks",
         light="Bright direct", soil="Cactus/succulent mix",
         temperature="65-75F", difficulty="Easy",
         summary="Thick woody stems and coin-shaped leaves; easy to propagate.",
         image_url="/static/assets/plants/jade_plant.jpg"),
    dict(common_name="Spider Plant", scientific_name="Chlorophytum comosum",
         category="Hanging", water="Medium - weekly",
         light="Bright indirect", soil="Standard potting mix",
         temperature="60-80F", difficulty="Easy",
         summary="Sends out baby 'pups' on runners; very forgiving.",
         image_url="/static/assets/plants/spider_plant.jpg"),
    dict(common_name="Basil", scientific_name="Ocimum basilicum",
         category="Herb", water="Medium - keep soil moist",
         light="Bright direct (6+ hrs)", soil="Well-draining potting mix",
         temperature="65-85F", difficulty="Medium",
         summary="Culinary herb; pinch flowers to keep leaves productive.",
         image_url="/static/assets/plants/basil.jpg"),
    dict(common_name="Orchid (Phalaenopsis)", scientific_name="Phalaenopsis amabilis",
         category="Flowering", water="Low - ice cube or weekly soak",
         light="Bright indirect", soil="Orchid bark mix",
         temperature="65-80F", difficulty="Medium",
         summary="Elegant blooms; roots need airflow, not regular soil.",
         image_url="/static/assets/plants/orchid.jpg"),
    dict(common_name="Rubber Plant", scientific_name="Ficus elastica",
         category="Tree", water="Medium - when top inch is dry",
         light="Bright indirect", soil="Well-draining potting mix",
         temperature="60-85F", difficulty="Easy",
         summary="Glossy burgundy-green leaves; wipe dust off for best growth.",
         image_url="/static/assets/plants/rubber_plant.jpg"),
    dict(common_name="Succulent Mix (Echeveria)", scientific_name="Echeveria elegans",
         category="Succulent", water="Low - every 2-3 weeks",
         light="Bright direct", soil="Cactus/succulent mix",
         temperature="65-80F", difficulty="Easy",
         summary="Rosette-shaped; prone to rot if watered from the top.",
         image_url="/static/assets/plants/echeveria.jpg"),
    dict(common_name="Venus Flytrap", scientific_name="Dionaea muscipula",
         category="Carnivorous", water="High - distilled water only, keep boggy",
         light="Bright direct", soil="Sphagnum moss / peat mix",
         temperature="70-90F", difficulty="Hard",
         summary="Needs distilled/rain water; tap water minerals will kill it.",
         image_url="/static/assets/plants/venus_flytrap.jpg"),
]


def seed():
    init_db()
    conn = get_db()
    conn.execute("DELETE FROM plants")
    conn.executemany(
        """
        INSERT INTO plants
            (common_name, scientific_name, category, water, light, soil,
             temperature, difficulty, summary, image_url)
        VALUES
            (:common_name, :scientific_name, :category, :water, :light, :soil,
             :temperature, :difficulty, :summary, :image_url)
        """,
        PLANTS,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) AS c FROM plants").fetchone()["c"]
    conn.close()
    print(f"Seeded {count} plants.")


if __name__ == "__main__":
    seed()
