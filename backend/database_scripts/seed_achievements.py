"""
Seed achievements into the database.

Run this script to populate the achievements table with all badge definitions
from the gamification plan.

Usage:
    python backend/seed_achievements.py
"""
import sys
import os

# Add project paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
sys.path.insert(0, os.path.dirname(__file__))

from app.config.database import SessionLocal
from app.models.gamification import Achievement
from app.services.achievement_definitions import ACHIEVEMENT_DEFINITIONS
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed_achievements():
    """Seed all achievement definitions into the database."""
    db = SessionLocal()
    
    try:
        created = 0
        updated = 0
        skipped = 0
        
        for defn in ACHIEVEMENT_DEFINITIONS:
            # Check if achievement already exists by name
            existing = db.query(Achievement).filter(
                Achievement.name == defn["name"]
            ).first()
            
            if existing:
                # Update existing achievement (in case definitions changed)
                existing.description = defn["description"]
                existing.category = defn["category"]
                existing.criteria = defn["criteria"]
                existing.reward_xp = defn["reward_xp"]
                existing.rarity = defn["rarity"]
                existing.icon_name = defn["icon_name"]
                existing.is_hidden = defn["is_hidden"]
                updated += 1
                logger.info(f"  Updated: {defn['name']}")
            else:
                # Create new achievement
                achievement = Achievement(
                    name=defn["name"],
                    description=defn["description"],
                    category=defn["category"],
                    criteria=defn["criteria"],
                    reward_xp=defn["reward_xp"],
                    rarity=defn["rarity"],
                    icon_name=defn["icon_name"],
                    is_hidden=defn["is_hidden"],
                )
                db.add(achievement)
                created += 1
                logger.info(f"  Created: {defn['name']}")
        
        db.commit()
        
        # Print summary
        total = db.query(Achievement).count()
        logger.info(f"\n{'='*50}")
        logger.info(f"Achievement Seeding Complete!")
        logger.info(f"  Created: {created}")
        logger.info(f"  Updated: {updated}")
        logger.info(f"  Total in database: {total}")
        logger.info(f"{'='*50}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding achievements: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting achievement seeding...")
    seed_achievements()
