FINAL_PROMPT = """
            User Question:
            {query}

            Sub-query Results (in no particular order):
            {structured_context}

            Instructions:
            - Answer the user's question using the results above.
            - Maintain the logical order of the user's question.
            - When answering multiple parts, respond in the same order they appear in the user question.
            - Ignore empty results.
            - If all results are empty, DO NOT GIVE EXPLANATIONS just say: No relevant data found.
            - Provide a clear and concise response.
            """