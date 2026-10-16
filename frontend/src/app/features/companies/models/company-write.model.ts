export interface CompanyCreate {
  name: string;
  code: string;
  description?: string | null;
}

// FastAPI accepts explicit nulls; name/code still have NOT NULL SQL constraints.
// Future forms must validate these fields without changing the transport contract.
export interface CompanyUpdate {
  name?: string | null;
  code?: string | null;
  description?: string | null;
}
