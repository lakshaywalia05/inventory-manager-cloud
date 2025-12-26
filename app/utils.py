import csv
from io import StringIO, BytesIO
from flask import send_file

def export_to_csv(data_list, filename):
    if not data_list:
        keys = ["id", "name", "price", "stock"] 
    else:
        keys = list(data_list[0].__dict__.keys())
        keys = [k for k in keys if not k.startswith('_')] 

    proxy = StringIO()
    writer = csv.writer(proxy)
    writer.writerow(keys) 
    
    for item in data_list:
        writer.writerow([getattr(item, key, '') for key in keys])
        
    proxy.seek(0)
    buffer = BytesIO(proxy.getvalue().encode('utf-8'))
    
    return send_file(buffer, mimetype='text/csv', as_attachment=True, download_name=f'{filename}.csv')

def import_csv_to_list(file_stream):
    stream = StringIO(file_stream.stream.read().decode("UTF8"))
    reader = csv.DictReader(stream)
    data_list = []
    for row in reader:
        data_list.append(dict(row))
    return data_list