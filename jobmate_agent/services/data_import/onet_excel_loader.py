"""
O*NET Excel Data Loader

This module provides functionality to load O*NET data from Excel files
(Occupation Data.xlsx, Task Statements.xlsx, Technology Skills.xlsx)
and normalize them by O*NET-SOC Code for embedding pipeline integration.

Key Features:
- Loads Excel files using pandas and openpyxl
- Normalizes all data by O*NET-SOC Code
- Returns structured data objects for embedding pipeline
- Handles data validation and error reporting

Usage:
    from jobmate_agent.services.data_import.onet_excel_loader import ONetExcelLoader

    loader = ONetExcelLoader(data_dir="./data")
    occupations = loader.load_all_occupations()
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ONetTechnologySkill:
    """Represents a technology skill from O*NET Technology Skills.xlsx"""

    name: str
    soc_code: str
    commodity_title: str
    hot_tech: bool = False
    in_demand: bool = False


@dataclass
class ONetOccupationContext:
    """Represents a complete occupation context with all related data"""

    soc_code: str
    occupation_title: str
    occupation_description: str
    task_statements: List[str] = field(default_factory=list)
    technology_skills: List[ONetTechnologySkill] = field(default_factory=list)


class ONetExcelLoader:
    """Loads O*NET data from Excel files and normalizes by SOC code."""

    def __init__(self, data_dir: str):
        """
        Initialize the O*NET Excel loader.

        Args:
            data_dir: Path to directory containing O*NET Excel files
        """
        self.data_dir = Path(data_dir)
        self.occupation_data = None
        self.task_data = None
        self.tech_skills_data = None

        # Validate files exist
        self._validate_files()

    def _validate_files(self) -> None:
        """Validate that required O*NET Excel files exist."""
        required_files = [
            "Occupation Data.xlsx",
            "Task Statements.xlsx",
            "Technology Skills.xlsx",
        ]

        missing_files = []
        for file_name in required_files:
            if not (self.data_dir / file_name).exists():
                missing_files.append(file_name)

        if missing_files:
            raise FileNotFoundError(
                f"Missing required O*NET Excel files: {', '.join(missing_files)}"
            )

        logger.info(f"Found all required O*NET Excel files in {self.data_dir}")

    def load_occupation_data(self) -> pd.DataFrame:
        """Load occupation data from Occupation Data.xlsx"""
        if self.occupation_data is not None:
            return self.occupation_data

        file_path = self.data_dir / "Occupation Data.xlsx"
        logger.info(f"Loading occupation data from {file_path}")

        try:
            df = pd.read_excel(file_path)
            logger.info(f"Loaded {len(df)} occupation records")

            # Log column names for debugging
            logger.debug(f"Occupation data columns: {df.columns.tolist()}")

            self.occupation_data = df
            return df

        except Exception as e:
            logger.error(f"Failed to load occupation data: {e}")
            raise

    def load_task_statements(self) -> pd.DataFrame:
        """Load task statements from Task Statements.xlsx"""
        if self.task_data is not None:
            return self.task_data

        file_path = self.data_dir / "Task Statements.xlsx"
        logger.info(f"Loading task statements from {file_path}")

        try:
            df = pd.read_excel(file_path)
            logger.info(f"Loaded {len(df)} task statement records")

            # Log column names for debugging
            logger.debug(f"Task data columns: {df.columns.tolist()}")

            self.task_data = df
            return df

        except Exception as e:
            logger.error(f"Failed to load task statements: {e}")
            raise

    def load_technology_skills(self) -> pd.DataFrame:
        """Load technology skills from Technology Skills.xlsx"""
        if self.tech_skills_data is not None:
            return self.tech_skills_data

        file_path = self.data_dir / "Technology Skills.xlsx"
        logger.info(f"Loading technology skills from {file_path}")

        try:
            df = pd.read_excel(file_path)
            logger.info(f"Loaded {len(df)} technology skill records")

            # Log column names for debugging
            logger.debug(f"Technology skills columns: {df.columns.tolist()}")

            self.tech_skills_data = df
            return df

        except Exception as e:
            logger.error(f"Failed to load technology skills: {e}")
            raise

    def normalize_by_soc_code(self) -> List[ONetOccupationContext]:
        """
        Load all Excel files and normalize by O*NET-SOC Code.

        Returns:
            List of ONetOccupationContext objects with all related data
        """
        logger.info("Loading and normalizing O*NET data by SOC code...")

        # Load all data
        occupations_df = self.load_occupation_data()
        tasks_df = self.load_task_statements()
        tech_skills_df = self.load_technology_skills()

        # Normalize column names (handle different possible column names)
        occupations_df = self._normalize_occupation_columns(occupations_df)
        tasks_df = self._normalize_task_columns(tasks_df)
        tech_skills_df = self._normalize_tech_skills_columns(tech_skills_df)

        # Group data by SOC code
        occupation_contexts = {}

        # Process occupations
        for _, row in occupations_df.iterrows():
            soc_code = row["soc_code"]
            occupation_contexts[soc_code] = ONetOccupationContext(
                soc_code=soc_code,
                occupation_title=row["title"],
                occupation_description=row.get("description", ""),
            )

        # Process task statements
        for _, row in tasks_df.iterrows():
            soc_code = row["soc_code"]
            if soc_code in occupation_contexts:
                occupation_contexts[soc_code].task_statements.append(row["task"])
            else:
                logger.warning(f"Task statement for unknown SOC code: {soc_code}")

        # Process technology skills
        for _, row in tech_skills_df.iterrows():
            soc_code = row["soc_code"]
            if soc_code in occupation_contexts:
                tech_skill = ONetTechnologySkill(
                    name=row["technology"],
                    soc_code=soc_code,
                    commodity_title=row.get("commodity_title", ""),
                    hot_tech=row.get("hot_tech", False),
                    in_demand=row.get("in_demand", False),
                )
                occupation_contexts[soc_code].technology_skills.append(tech_skill)
            else:
                logger.warning(f"Technology skill for unknown SOC code: {soc_code}")

        # Convert to list and sort by SOC code
        result = list(occupation_contexts.values())
        result.sort(key=lambda x: x.soc_code)

        logger.info(f"Normalized {len(result)} occupation contexts")
        return result

    def _normalize_occupation_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize occupation data column names."""
        # Map common column name variations
        column_mapping = {
            "O*NET-SOC Code": "soc_code",
            "ONET-SOC Code": "soc_code",
            "SOC Code": "soc_code",
            "Title": "title",
            "Occupation Title": "title",
            "Description": "description",
            "Occupation Description": "description",
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required_columns = ["soc_code", "title"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required occupation columns: {missing_columns}")

        # Fill missing description with empty string
        if "description" not in df.columns:
            df["description"] = ""

        return df

    def _normalize_task_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize task statements column names."""
        # Map common column name variations
        column_mapping = {
            "O*NET-SOC Code": "soc_code",
            "ONET-SOC Code": "soc_code",
            "SOC Code": "soc_code",
            "Task": "task",
            "Task Statement": "task",
            "Statement": "task",
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required_columns = ["soc_code", "task"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required task columns: {missing_columns}")

        return df

    def _normalize_tech_skills_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize technology skills column names."""
        # Map common column name variations
        column_mapping = {
            "O*NET-SOC Code": "soc_code",
            "ONET-SOC Code": "soc_code",
            "SOC Code": "soc_code",
            "Technology": "technology",
            "Example": "technology",
            "Tech Example": "technology",
            "Commodity Title": "commodity_title",
            "Commodity": "commodity_title",
            "Hot Technology": "hot_tech",
            "Hot Tech": "hot_tech",
            "In Demand": "in_demand",
            "In-Demand": "in_demand",
        }

        # Rename columns
        df = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required_columns = ["soc_code", "technology"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(
                f"Missing required technology skills columns: {missing_columns}"
            )

        # Set defaults for optional columns
        if "commodity_title" not in df.columns:
            df["commodity_title"] = ""
        if "hot_tech" not in df.columns:
            df["hot_tech"] = False
        if "in_demand" not in df.columns:
            df["in_demand"] = False

        # Convert boolean columns
        df["hot_tech"] = df["hot_tech"].map(
            lambda x: str(x).lower() in ["true", "1", "yes", "y"]
        )
        df["in_demand"] = df["in_demand"].map(
            lambda x: str(x).lower() in ["true", "1", "yes", "y"]
        )

        return df

    def load_all_occupations(self) -> List[ONetOccupationContext]:
        """Load all occupation contexts with normalized data."""
        return self.normalize_by_soc_code()

    def get_occupation_by_soc_code(
        self, soc_code: str
    ) -> Optional[ONetOccupationContext]:
        """Get a specific occupation context by SOC code."""
        occupations = self.load_all_occupations()
        for occupation in occupations:
            if occupation.soc_code == soc_code:
                return occupation
        return None

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded data."""
        occupations = self.load_all_occupations()

        total_tasks = sum(len(occ.task_statements) for occ in occupations)
        total_tech_skills = sum(len(occ.technology_skills) for occ in occupations)
        hot_tech_count = sum(
            sum(1 for tech in occ.technology_skills if tech.hot_tech)
            for occ in occupations
        )
        in_demand_count = sum(
            sum(1 for tech in occ.technology_skills if tech.in_demand)
            for occ in occupations
        )

        return {
            "total_occupations": len(occupations),
            "total_task_statements": total_tasks,
            "total_technology_skills": total_tech_skills,
            "hot_technologies": hot_tech_count,
            "in_demand_skills": in_demand_count,
            "avg_tasks_per_occupation": (
                total_tasks / len(occupations) if occupations else 0
            ),
            "avg_tech_skills_per_occupation": (
                total_tech_skills / len(occupations) if occupations else 0
            ),
        }
