import json
from openai import OpenAI
import streamlit as st

from openai import OpenAI


from pymongo import MongoClient

# Initialize MongoDB client (Replace with your MongoDB URI)
mongo_client = MongoClient(st.secrets["MONGO_DB_URI"])
db = mongo_client[st.secrets["MONGO_DB_DATABASE_NAME"]]
collection = db[st.secrets["MONGO_DB_COLLECTION_NAME"]]

client = OpenAI(api_key = st.secrets["OPENAI_API_KEY"])


def get_function_output(function_name, function_arguments):

    if function_name=="Search_Niagara_Documents":
        function_arguments = json.loads(function_arguments)
        search_terms = function_arguments["search_terms"]
        return Search_Niagara_Documents(search_terms=search_terms)
        
    

    return "results are not currently available"


def Search_Niagara_Documents(search_terms , max_output=25):

    embedding_response = client.embeddings.create(
        model = "text-embedding-ada-002",
        input = search_terms

    )

    embedding = embedding_response.data[0].embedding


    normal_search_results = get_normal_search_results(search_terms)
    print(len(normal_search_results))
    vector_search_results = get_vector_search_results(embedding)

    result_map = {}

    # Aggregate scores from normal search results
    for result in normal_search_results:
        normalized_score = result['score']  # Additional normalization can be done if needed
        if result['text'] in result_map:
            result_map[result['text']] += normalized_score
        else:
            result_map[result['text']] = normalized_score

    # Aggregate scores from vector search results
    for result in vector_search_results:
        normalized_score = result['score']  # Additional normalization can be done if needed
        if result['text'] in result_map:
            result_map[result['text']] += normalized_score
        else:
            result_map[result['text']] = normalized_score

    # Step 5: Sort the fused list by score in descending order
    fused_list = sorted(
        [{"text": text, "score": score} for text, score in result_map.items()],
        key=lambda x: x["score"],
        reverse=True
    )

    # Step 6: Limit the results to max_output
    top_results = fused_list[:max_output]

    # Step 7: Return the top results as a string
    return ', '.join(item['text'] for item in top_results)



def getNiagaraCollection():
    return collection

def get_normal_search_results(query, limit=25):
    """
    Fetch normal search results based on textual matching.
    """
    try:
        collection = getNiagaraCollection()

        # Define the aggregation pipeline for normal search
        pipeline = [
            {
                "$search": {
                    "index": "default",
                    "text": {
                        "query": query,
                        "path": "contextual_text"
                    }
                }
            },
            {"$limit": limit},
            {
                "$project": {
                    "contextual_text": 1,
                    "original_text": 1,
                    "document_name": 1,
                    "page_number": 1,
                    "score": {"$meta": "searchScore"}
                }
            },
            {"$sort": {"score": -1}}
        ]

        # Run the aggregation pipeline
        print("here , Trying to the call the pipeline" )
        results = list(collection.aggregate(pipeline))

        # Format the results
        formatted_results = [
            {
                "score": result["score"],
                "text": f"Original Text : {result['original_text']} (Document: {result['document_name']}, Page: {result['page_number']} , Context of Text : {result['contextual_text']})"
            }
            for result in results
        ]

        return formatted_results

    except Exception as error:
        print(f"Error fetching normal search results: {error}")
        return []

def get_vector_search_results(embeddings, limit=25, num_candidates=100):
    """
    Fetch vector search results based on vector embeddings.
    """
    try:
        collection = getNiagaraCollection()

        # Define the aggregation pipeline for vector search
        pipeline = [
            {
                "$vectorSearch": {
                    "index": "vector_index",
                    "path": "vector_embeddings",
                    "queryVector": embeddings,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$project": {
                    "contextual_text": 1,
                    "original_text": 1,
                    "document_name": 1,
                    "page_number": 1,
                    "score": {"$meta": "searchScore"}
                }
            },
            {"$sort": {"score": -1}}
        ]

        # Run the aggregation pipeline
        results = list(collection.aggregate(pipeline))
        print("##Results from vector store")
        print(len(results) )
        print(results[0])
        # Format the results
        formatted_results = [
            {
                "score": result.get("score", 1),
                "text": f"Original Text : {result['original_text']} (Document: {result['document_name']}, Page: {result['page_number']} , Context of Text : {result['contextual_text']})"
            }
            for result in results
        ]

        return formatted_results

    except Exception as error:
        print(f"Error fetching vector search results: {error}")
        return []


    
