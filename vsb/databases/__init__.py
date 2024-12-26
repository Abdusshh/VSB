from enum import Enum
from .base import DB


class Database(Enum):
    """Set of supported database backends, the value is the string used to
    specify via --database="""

    Pinecone = "pinecone"
    PGVector = "pgvector"
    Upstash = "upstash"
    Supabase = "supabase"

    def get_class(self) -> type[DB]:
        """Return the DB class to use, based on the value of the enum"""
        match self:
            case Database.Pinecone:
                from .pinecone.pinecone import PineconeDB

                return PineconeDB
            case Database.PGVector:
                from .pgvector.pgvector import PgvectorDB

                return PgvectorDB
            case Database.Upstash:
                from .upstash.upstash import UpstashDB
                
                return UpstashDB
            case Database.Supabase:
                from .supabase.supabase import SupabaseDB

                return SupabaseDB
            
