class NoSQLSchemaExtractor:
    def __init__(self):
        self.EXTRACTOR_MAP = {
        "mongodb": self._extract_mongo
    }

    async def extract_schema(self, conn_info):

        db_type = conn_info["db_type"]
        connection = conn_info["connection"]

        extractor = self.EXTRACTOR_MAP.get(db_type)
        
        try:
            return await extractor(connection)
        except Exception as e:
            return {
                "error": f"Schema extraction failed: {str(e)}"
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
