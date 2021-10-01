import os
import pathlib
import shutil
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, cross_val_score
import pyarrow as pa
from pyarrow import parquet
import joblib


def data_extraction(*args, **kwargs):
    """Extract data
    In this example, it will copy data from source folder to intermedia folder
    """
    print(f'Run data_extraction with run_id: {kwargs["dag_run"].run_id}')
    assert os.environ.get("DATA_SOURCE_FOLDER")
    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    from_path = pathlib.Path(
        os.environ.get("DATA_SOURCE_FOLDER"), "winequality-red.csv"
    )
    to_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"), kwargs["dag_run"].run_id
    )
    to_path.mkdir(parents=True, exist_ok=True)
    shutil.copy(from_path, to_path)


def data_validation(*args, **kwargs):
    """Data validation
    """
    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    input_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"),
        kwargs["dag_run"].run_id,
        "winequality-red.csv",
    )
    wine = pd.read_csv(input_path)
    print(wine.head())
    print(wine.info())


def _1d_nparray_to_parquet(array, path):
    table = pa.Table.from_arrays([array], ["0"],)
    parquet.write_table(table, path)


def _2d_nparray_to_parquet(array, path):
    table = pa.Table.from_arrays(
        array, names=[str(i) for i in range(len(array))],  # give names to each columns
    )
    parquet.write_table(table, path)


def data_preparation(*args, **kwargs):
    """Data preparation
    """

    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    run_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"), kwargs["dag_run"].run_id
    )
    input_path = pathlib.Path(run_path, "winequality-red.csv",)
    wine = pd.read_csv(input_path)

    # Now seperate the dataset as response variable and feature variabes
    X = wine.drop("quality", axis=1)
    y = wine["quality"]

    # Train and Test splitting of data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Applying Standard scaling to get optimized result
    sc = StandardScaler()

    X_train = sc.fit_transform(X_train)
    X_test = sc.fit_transform(X_test)

    print(f"x train shape: {X_train.shape}")
    print(f"x train head: {X_train[:10]}")
    print(f"x test shape: {X_test.shape}")
    print(f"y train shape: {y_train.shape}")
    print(f"y train head: {y_train[:10]}")
    print(f"y test shape: {y_test.shape}")

    # Save the train and test set to parquet for next task
    _2d_nparray_to_parquet(X_train, pathlib.Path(run_path, "x_train.parquet"))
    _2d_nparray_to_parquet(X_test, pathlib.Path(run_path, "x_test.parquet"))
    _1d_nparray_to_parquet(y_train, pathlib.Path(run_path, "y_train.parquet"))
    _1d_nparray_to_parquet(y_test, pathlib.Path(run_path, "y_test.parquet"))


def _parquet_to_2d_nparray(path):
    table_from_parquet = parquet.read_table(path)
    matrix_from_parquet = table_from_parquet.to_pandas().T.to_numpy()
    return matrix_from_parquet


def _parquet_to_1d_nparray(path):
    table_from_parquet = parquet.read_table(path)
    matrix_from_parquet = table_from_parquet.to_pandas().T.to_numpy()
    return matrix_from_parquet[0]


def model_training(*args, **kwargs):
    """Model training
    """
    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    run_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"), kwargs["dag_run"].run_id
    )
    X_train = _parquet_to_2d_nparray(pathlib.Path(run_path, "x_train.parquet"))
    X_test = _parquet_to_2d_nparray(pathlib.Path(run_path, "x_test.parquet"))
    y_train = _parquet_to_1d_nparray(pathlib.Path(run_path, "y_train.parquet"))
    y_test = _parquet_to_1d_nparray(pathlib.Path(run_path, "y_test.parquet"))
    print(f"x train shape: {X_train.shape}")
    print(f"x train head: {X_train[:10]}")
    print(f"x test shape: {X_test.shape}")
    print(f"y train shape: {y_train.shape}")
    print(f"y train head: {y_train[:10]}")
    print(f"y test shape: {y_test.shape}")

    rfc = RandomForestClassifier(n_estimators=200)
    rfc.fit(X_train, y_train)
    joblib.dump(rfc, pathlib.Path(run_path, "random_forest_model.sav"))


def model_evaluation(*args, **kwargs):
    """Model evaluation
    """
    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    run_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"), kwargs["dag_run"].run_id
    )
    X_train = _parquet_to_2d_nparray(pathlib.Path(run_path, "x_train.parquet"))
    y_train = _parquet_to_1d_nparray(pathlib.Path(run_path, "y_train.parquet"))
    rfc = joblib.load(pathlib.Path(run_path, "random_forest_model.sav"))

    # Now lets try to do some evaluation for random forest model using cross validation.
    rfc_eval = cross_val_score(estimator=rfc, X=X_train, y=y_train, cv=10)
    print(f"Random forest model: {rfc_eval.mean()}")


def model_validation(*args, **kwargs):
    """Model validation
    """
    assert os.environ.get("DATA_INTERMEDIA_FOLDER")
    run_path = pathlib.Path(
        os.environ.get("DATA_INTERMEDIA_FOLDER"), kwargs["dag_run"].run_id
    )
    X_test = _parquet_to_2d_nparray(pathlib.Path(run_path, "x_test.parquet"))
    y_test = _parquet_to_1d_nparray(pathlib.Path(run_path, "y_test.parquet"))

    rfc = joblib.load(pathlib.Path(run_path, "random_forest_model.sav"))

    pred_rfc = rfc.predict(X_test)
    print("\n" + classification_report(y_test, pred_rfc))
