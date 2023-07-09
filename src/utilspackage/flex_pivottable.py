import pandas as pd
import numpy as np
from django.apps import apps
from django.shortcuts import HttpResponse, render
from ddrug.utils.bio_data import agg_Lst, agg_DR, agg_Inhib

#    #-------------------------------------------------------------------------------------------------
# data-visulization 
def get_pivottable(querydata=None, aggfunc_name=None, columns_str=None, index_str=None, values=None):
    aggfunc={'String_concat':lambda x:  " ".join([str(y) for y in x]), 'Lst': agg_Lst, 'DR': agg_DR, 'Inhib':agg_Inhib}
    data=querydata #
    df=pd.DataFrame(data)
    df.reset_index
    df.fillna(0)
    
    columns=columns_str.split(",") 
    index=index_str.split(",")
    
    try:
        table=pd.pivot_table(df, values=values, index=index,
                       columns=columns, aggfunc=aggfunc[aggfunc_name], fill_value=0)#np_aggfunc[aggfunc], fill_value='0')
    except Exception as err:
        print(f'err is {err}')
        table=err
    return table
# Return styled pivoted table
def flex_pivottable(request,app_model):
    table_html = None

    model_name = app_model.split("-")[1]
    app_name = app_model.split("-")[0]

    try:
        Model = apps.get_model(app_name, model_name)
    except LookupError:
        # Handle the case where the model does not exist.
        return HttpResponse("Model not found.")
    model_fields=[f.replace(".", "__") for f in list(Model.HEADER_FIELDS.keys())] #list(Model.HEADER_FIELDS.keys())
    pk_list = request.session.get(f'{Model}_cached_queryset')
    
    if request.method == "POST": # 
        
        values_str = request.POST.get("values") or None  # or "n_left"
        columns_str =request.POST.get("column") or None # or "orgbatch_id"
        index_str = request.POST.get("index") or None
        aggfunc_name = request.POST.get("data_function_type") or None
        # get queryset
        queryset = Model.objects.filter(pk__in=pk_list) if pk_list else Model.objects.all()
        # flatten the queryset to put it in dataframe
        querylist=queryset.values_list(*model_fields)
        data={}
        for num_fields in range(len(model_fields)):
            arrary=[querylist[i][num_fields] for i in range(len(querylist))]
            data[model_fields[num_fields]]=arrary
        values = values_str or None  # pivottable values
        
        if values:
            try:
                table =get_pivottable(querydata=data, aggfunc_name=aggfunc_name, columns_str=columns_str, index_str=index_str, values=values) 

                # response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                # response['Content-Disposition'] = f'attachment; filename="{filename}.xlsx"'
                try:
                    # table_excel = table.to_excel(excel_writer=response, index=False)
                    # request.cache.set(f"{request.user}_pivoteddata": )
                    table_html = table.head(n=50).to_html(classes=["table", "table-bordered", "fixTableHead"])
                except Exception as err:
                    table_html = f"<span class='text-danger'>something wrong with {table}</span>"
 

            except Exception as err:
                error_message = f"error is {err}"
                table_html= f"error is {err}"
       

    return render(request, 'utils/pivotedtable.html', {"table":table_html, "app_model":app_model, "model_fields":model_fields, "query_list": pk_list})