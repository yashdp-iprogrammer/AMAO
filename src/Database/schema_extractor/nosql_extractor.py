from src.utils.logger import logger

class NoSQLSchemaExtractor:
    def __init__(self):
        self.EXTRACTOR_MAP = {
            "mongo": self._extract_mongo
        }

    async def extract_schema(self, conn_info):

        db_type = conn_info["db_type"]
        connection = conn_info["connection"]

        extractor = self.EXTRACTOR_MAP.get(db_type)

        if not extractor:
            logger.warning(f"[NoSQLSchemaExtractor] Unsupported db_type: {db_type}")
            return {"error": f"Unsupported db_type: {db_type}"}

        logger.info(f"[NoSQLSchemaExtractor] Extracting schema for db_type: {db_type}")

        try:
            return await extractor(connection)

        except Exception:
            logger.exception(f"[NoSQLSchemaExtractor] Schema extraction failed for db_type: {db_type}")
            return {
                "error": "Schema extraction failed"
            }

    # -------------------------
    # Mongo
    # -------------------------
    async def _extract_mongo(self, db):

        collections = await db.list_collection_names()

        schema = {}

        for col in collections:

            doc = await db[col].find_one()

            if doc:
                schema[col] = list(doc.keys())
            else:
                schema[col] = []

        return schema
