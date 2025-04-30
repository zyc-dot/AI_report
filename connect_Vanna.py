from vanna.remote import VannaDefault


def db_connect(model_name, api_key, host, user, password, port, dbname):
    vn = VannaDefault(model=model_name, api_key=api_key)
    vn.connect_to_mysql(
        host=host,
        user=user,
        password=password,
        port=port,
        dbname=dbname
    )
    return vn
