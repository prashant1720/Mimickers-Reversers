import pandas as pd
from flask import Flask, render_template, request, send_from_directory, jsonify
import json
import requests
import os
import uuid
from flask_cors import CORS


app = Flask(__name__)
CORS(app)
df = pd.DataFrame(columns=['up', 'down'])
@app.route('/api/mimickers', methods=['GET', 'POST'])
def my_route():

    if request.method == 'POST':

  
        up_genes = request.form['up_genes']
        down_genes = request.form['down_genes']

        up_values = [s.strip().strip("'") for s in up_genes.split(',')]
        down_values = [s.strip().strip("'") for s in down_genes.split(',')]
    
        df = pd.DataFrame({'Up': up_values, 'Down': down_values})
        df
       # create the DataFrame with the input values
        df = pd.DataFrame({'Up': up_values, 'Down': down_values})
        up = df['Up']
        down = df['Down']
        up_list= list(up)
        up_list = list(filter(pd.notnull, up_list))
        down_list= list(down)
        down_list = list(filter(pd.notnull, down_list))
    

        METADATA_API = "https://maayanlab.cloud/sigcom-lincs/metadata-api/"
        DATA_API = "https://maayanlab.cloud/sigcom-lincs/data-api/api/v1/"

        input_gene_set = {
            "up_genes": up_list,
            "down_genes": down_list
        }

        all_genes = input_gene_set["up_genes"] + input_gene_set["down_genes"]

        payload = {
            "filter": {
                "where": {
                    "meta.symbol": {
                        "inq": all_genes
                    }
                },
                "fields": ["id", "meta.symbol"]
            }
        }
        res = requests.post(METADATA_API + "entities/find", json=payload)
        entities = res.json()

        for_enrichment = {
            "up_entities": [],
            "down_entities": []
        }

        for e in entities:
            symbol = e["meta"]["symbol"]
            if symbol in input_gene_set["up_genes"]:
                for_enrichment["up_entities"].append(e["id"])
            elif symbol in input_gene_set["down_genes"]:
                for_enrichment["down_entities"].append(e["id"])

        payload = {
            "meta": {
                "$validator": "/dcic/signature-commons-schema/v6/meta/user_input/user_input.json",
                **for_enrichment
            },
            "type": "signature"
        }
        res = requests.post(METADATA_API + "user_input", json=payload)
        persistent_id = res.json()["id"]
        query = {
            **for_enrichment,
            "limit": 10,
            "database": "l1000_cp"
        }

        res = requests.post(DATA_API + "enrich/ranktwosided", json=query)
        results = res.json()

        # Optional, multiply z-down and direction-down with -1
        for i in results["results"]:
            i["z-down"] = -i["z-down"]
            i["direction-down"] = -i["direction-down"]
        sigids = {i["uuid"]: i for i in results["results"]}

        payload = {
            "filter": {
                "where": {
                    "id": {
                        "inq": list(sigids.keys())
                    }
                }
            }
        }
        res = requests.post(METADATA_API + "signatures/find", json=payload)
        signatures = res.json()

        ## Merge the scores and the metadata
        for sig in signatures:
            uid = sig["id"]
            scores = sigids[uid]
            scores.pop("uuid")
            sig["scores"] = scores

        de = pd.DataFrame(columns=["Type", "Pert Name"])

        # Loop through the results and append each row to the DataFrame
        for result in signatures:
            result_type = result["scores"]["type"]
            result_pert_name = result["meta"]["pert_name"]
            print()
            de = de.append({"Type": result_type, "Pert Name": result_pert_name}, ignore_index=True)

        mimickers_df = de.loc[de['Type'] == 'mimickers', ['Pert Name']]
        reversers_df = de.loc[de['Type'] == 'reversers', ['Pert Name']]

        mimickers_df.reset_index(inplace=True, drop=True)

        reversers_df.reset_index(inplace=True, drop=True)

        # Rename the columns to 'mimickers' and 'reversers'
        mimickers_df.columns = ['mimickers']
        reversers_df.columns = ['reversers']

        # Concatenate the two dataframes horizontally
        result_df = pd.concat([mimickers_df, reversers_df], axis=1)
        html_table = result_df.to_html(index=False)

        # Save the resulting dataframe to a CSV file
        filename = str(uuid.uuid4()) + '.csv'
        result_df.to_csv(os.path.join(
            app.root_path, 'download', filename), index=False)

        return render_template('nlp.html',filename=filename,html_table=html_table)
    else:
        return render_template('nlp.html')



@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(os.path.join(app.root_path, 'download'), filename)







# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    app.run(debug=True)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
