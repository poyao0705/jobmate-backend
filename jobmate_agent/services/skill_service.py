from dataclasses import dataclass
from typing import Optional, List
from sqlalchemy import text, func
import numpy as np

# LangChain & Models
from langchain_openai import OpenAIEmbeddings
from app.models import db, Skill, SkillAlias

# --- 1. The Data Transfer Object (DTO) ---
@dataclass
class SkillMatchResult:
    skill: Optional[Skill]  # The DB object (None if no match found)
    raw_text: str           # The input text ("ReactJS")
    score: float            # Similarity score (0.0 to 1.0)
    is_confident: bool      # True if score > threshold

# --- 2. The Service Class ---
class SkillService:
    def __init__(self):
        # Initialize the embedding model once (Singleton pattern recommended)
        self.embedding_model = OpenAIEmbeddings(model="text-embedding-3-large")

    # --- CORE HELPER: Get Vector ---
    def _get_embedding(self, text_content: str) -> List[float]:
        """
        Wraps the API call to handle potential errors or caching in the future.
        """
        return self.embedding_model.embed_query(text_content)

    # --- FUNCTION A: Add New Skill (Admin/System) ---
    def add_new_skill(self, name: str, description: str = "", category: str = "general") -> Optional[Skill]:
        """
        Creates a new skill and generates its vector embedding with context.
        """
        # Context Injection: "Go" -> "Go: A programming language..."
        text_to_embed = f"{name}: {description}" if description else name
        vector = self._get_embedding(text_to_embed)

        new_skill = Skill(
            name=name,
            description=description,
            embedding=vector, # Requires pgvector column
            metadata_json={"category": category}
        )

        try:
            db.session.add(new_skill)
            db.session.commit()
            return new_skill
        except Exception as e:
            db.session.rollback()
            print(f"Error adding skill: {e}")
            return None

    # --- FUNCTION B: Normalize (The "One True ID" Finder) ---
    def normalize_skill(self, raw_text: str, threshold=0.80) -> SkillMatchResult:
        """
        Used by Resume Parser & Job Saver.
        Strategy: 1. Exact SQL Match -> 2. Alias Match -> 3. Vector Search
        """
        clean_text = raw_text.strip()

        # 1. TIER 1: Exact Match (Case Insensitive)
        # Checks 'React' == 'react'
        exact_match = Skill.query.filter(
            func.lower(Skill.name) == func.lower(clean_text)
        ).first()

        if exact_match:
            return SkillMatchResult(exact_match, raw_text, 1.0, True)

        # 2. TIER 2: Alias Match
        # Checks 'ReactJS' -> Alias('ReactJS') -> Skill('React.js')
        alias_match = SkillAlias.query.filter(
            func.lower(SkillAlias.name) == func.lower(clean_text)
        ).first()

        if alias_match:
            return SkillMatchResult(alias_match.skill, raw_text, 1.0, True)

        # 3. TIER 3: Vector Search (Fuzzy Match)
        # Only runs if Tier 1 & 2 fail.
        return self._perform_vector_search(clean_text, limit=1, threshold=threshold)

    # --- FUNCTION C: Search (The "Browser") ---
    def find_similar_skills(self, user_query: str, limit=5) -> List[SkillMatchResult]:
        """
        Used by Chatbot suggestions.
        Returns a LIST of matches, not just one.
        """
        # Search implies we go straight to vectors (semantic exploration)
        # But we wrap the single result in a list helper
        return self._perform_vector_search_list(user_query, limit)

    # --- INTERNAL: Vector Search Logic ---
    def _perform_vector_search(self, text_input: str, limit: int, threshold: float) -> SkillMatchResult:
        """
        Internal helper to run the SQL Vector query for a single best match.
        """
        # Synthetic Context: If input is tiny ("Go"), help the vector.
        query_text = f"{text_input} technology skill" if len(text_input) < 4 else text_input
        query_vector = self._get_embedding(query_text)

        # PGVector Query
        # We explicitly select the distance (1 - distance = similarity)
        sql = text("""
            SELECT id, name, description, 1 - (embedding <=> :vec) as similarity
            FROM skills
            ORDER BY embedding <=> :vec
            LIMIT :limit
        """)

        # Execute
        row = db.session.execute(sql, {'vec': str(query_vector), 'limit': limit}).first()

        if not row:
            return SkillMatchResult(None, text_input, 0.0, False)

        # Rehydrate Skill Object
        skill_obj = Skill(id=row.id, name=row.name, description=row.description)
        score = float(row.similarity)

        return SkillMatchResult(
            skill=skill_obj,
            raw_text=text_input,
            score=score,
            is_confident=(score >= threshold)
        )

    def _perform_vector_search_list(self, text_input: str, limit: int) -> List[SkillMatchResult]:
        """
        Internal helper to return multiple results.
        """
        query_vector = self._get_embedding(text_input)
        
        sql = text("""
            SELECT id, name, description, 1 - (embedding <=> :vec) as similarity
            FROM skills
            ORDER BY embedding <=> :vec
            LIMIT :limit
        """)

        rows = db.session.execute(sql, {'vec': str(query_vector), 'limit': limit}).fetchall()
        
        results = []
        for row in rows:
            skill_obj = Skill(id=row.id, name=row.name, description=row.description)
            results.append(SkillMatchResult(
                skill=skill_obj,
                raw_text=text_input,
                score=float(row.similarity),
                is_confident=(float(row.similarity) > 0.80)
            ))
            
        return results

# Singleton Instance
skill_service = SkillService()