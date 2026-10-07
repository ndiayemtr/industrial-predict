import pandas as pd


class TemporalDatasetSplitter:

    def split(
        self,
        dataframe: pd.DataFrame,
        *,
        train_ratio: float = 0.6,
        validation_ratio: float = 0.2,
    ) -> tuple[
        pd.DataFrame,
        pd.DataFrame,
        pd.DataFrame,
    ]:

        if dataframe.empty:
            return (
                dataframe.copy(),
                dataframe.copy(),
                dataframe.copy(),
            )

        if not 0 < train_ratio < 1:
            raise ValueError(
                "train_ratio must be between 0 and 1"
            )

        if not 0 <= validation_ratio < 1:
            raise ValueError(
                "validation_ratio must be between 0 and 1"
            )

        if train_ratio + validation_ratio >= 1:
            raise ValueError(
                "train_ratio + validation_ratio must be less than 1"
            )

        if "timestamp" not in dataframe.columns:
            raise ValueError(
                "Missing required column: timestamp"
            )

        result = dataframe.copy()

        result["timestamp"] = pd.to_datetime(
            result["timestamp"],
            utc=True,
        )

        result = result.sort_values(
            by="timestamp"
        ).reset_index(drop=True)

        row_count = len(result)

        train_end = int(
            row_count * train_ratio
        )

        validation_end = (
            train_end
            + int(row_count * validation_ratio)
        )

        train = result.iloc[
            :train_end
        ].copy()

        validation = result.iloc[
            train_end:validation_end
        ].copy()

        test = result.iloc[
            validation_end:
        ].copy()

        return (
            train,
            validation,
            test,
        )