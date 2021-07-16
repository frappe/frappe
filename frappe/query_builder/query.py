import sqlalchemy

class qb: 
    def __init__(self, db_type, user: str, password: str):
        self.db_type = db_type

        if self.db_type == 'mariadb':
            self.engine = sqlalchemy.create_engine(f"mariadb+mariadbconnector://{user}:{password}@127.0.0.1:3306/_e21fc56c1a272b63")
        if self.db_type == 'postgres':
            self.engine = sqlalchemy.create_engine(f"postgresql://{user}:{password}@localhost/_9b466094ec991a03")


    def get_reflection(self, table_name):
        return sqlalchemy.Table(table_name, sqlalchemy.MetaData(), autoload_with=self.engine)

    def get_values(self, query: str):
        query = query.compile(compile_kwargs={"literal_binds": True})
        return str(query)
        
