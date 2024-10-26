import streamlit as st
import pandas as pd
import altair as alt
import base64
from io import BytesIO
from PIL import Image
from openai import OpenAI
import time

from utils import get_function_output
# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# Function to encode image in base64
def encode_image(image):
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode("utf-8")

# Set up the layout with two columns
col1, col2 = st.columns(2)

# Available chart types
chart_types = ["Line", "Scatter", "Bar", "Area"]

# Column 1: Table input and chart type selection
with col1:
    st.write("### Enter Data for Graph")
    
    # Input for custom column names
    x_column = st.text_input("X-axis Column Name", "date")
    y_column = st.text_input("Y-axis Column Name", "bottle pressure")

    # Select the chart type
    chart_type = st.selectbox("Choose Chart Type", chart_types)

    # Enter the graph query
    query = st.text_input("Query about the data", "Please Summarize this graph in light of Niagara Bottling Quality Standards")

    # Create an editable table with default data
    data = pd.DataFrame({
        "date": ["4/1/2024  12:21:53 AM", "4/1/2024  1:01:18 AM", "4/1/2024  2:01:21 AM", "4/1/2024  3:11:15 AM", "4/1/2024  4:10:04 AM" , "4/1/2024  6:03:39 AM" , "4/1/2024  7:00:17 AM" , "4/1/2024  8:00:01 AM"],
        "bottle pressure": [2.97, 4.26, 4.1, 2.02, 5.11 , 4.99 , 3.89 , 4.05]
    })
    edited_data = st.data_editor(data, num_rows="dynamic")
# Column 2: Graph display
with col2:
    st.write("### Dynamic Graph")
    
    # Plot the graph using Altair based on chosen chart type
    if chart_type == "Line":
        chart = alt.Chart(edited_data).mark_line().encode(
            x=x_column,
            y=y_column
        )
    elif chart_type == "Scatter":
        chart = alt.Chart(edited_data).mark_point().encode(
            x=x_column,
            y=y_column
        )
    elif chart_type == "Bar":
        chart = alt.Chart(edited_data).mark_bar().encode(
            x=x_column,
            y=y_column
        )
    elif chart_type == "Area":
        chart = alt.Chart(edited_data).mark_area().encode(
            x=x_column,
            y=y_column
        )

    # Set chart properties and display it
    chart = chart.properties(width=400, height=300)
    st.altair_chart(chart, use_container_width=True)

# Button to send the graph to OpenAI
if st.button("Send Graph"):
    # Save Altair chart as image and encode to base64
    chart_path = "./temp_chart.png"
    chart.save(chart_path)
    
    # Open and encode the image in base64
    with open(chart_path, "rb") as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')
    bot_response = ""
    with st.status("Getting Graph Summary from IN-Q Center" , expanded=True) as status:
        st.write("Uploading Graph to In-Q Center")
        file = client.files.create(file = open(chart_path , "rb") , purpose = "vision")
        st.write("Creating new thread in OpenAI")
        thread = client.beta.threads.create(
            messages = [
                {
                    "role" : "user",
                    "content" : [
                        {
                            "type" : "text",
                            "text" : query
                        },
                        {
                            "type" : "image_file",
                            "image_file" : {"file_id" : file.id}
                        }
                    ]
                }
            ]
        )
        st.write("Awaiting response from In-Q Center")
        run = client.beta.threads.runs.create(
            thread_id = thread.id,
            assistant_id = st.secrets["OPENAI_ASSISTANT_ID"],
            tool_choice = {"type": "function", "function": {"name": "Search_Niagara_Documents"}}
        )
        while run.status not in ["cancelled" , "completed" , "failed" ]:

            run = client.beta.threads.runs.retrieve(
                thread_id = thread.id,
                run_id = run.id
            )
            print(run.id , run.status)
            if run.status == "requires_action":
                tool_calls = run.required_action.submit_tool_outputs.tool_calls

                tool_outputs = []

                for tool_call in tool_calls:
                    tool_call_id = tool_call.id
                    function_name = tool_call.function.name
                    function_arguments = tool_call.function.arguments

                    output = get_function_output(function_name , function_arguments)

                    tool_outputs.append({"tool_call_id" : tool_call_id , "output" : output})


                run = client.beta.threads.runs.submit_tool_outputs(
                    thread_id = thread.id,
                    run_id = run.id,
                    tool_outputs = tool_outputs
                )

            time.sleep(5)
        
        if run.status=="completed":
            thread_messages = client.beta.threads.messages.list(thread.id)
            bot_response = thread_messages.data[0].content[0].text.value
            print(bot_response)
        else:
            st.write("Error occured in getting response from openai")
            bot_response="Error"

        st.write("Done")
        
    st.markdown(bot_response)