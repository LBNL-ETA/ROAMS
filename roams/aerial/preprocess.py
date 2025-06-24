import pandas as pd

def account_for_cutoffs(
        plumes : pd.DataFrame, 
        cutoff_col : str, 
        wind_normalized_em_col : str,
    ) -> pd.DataFrame:
    """
    Look for a `cutoff_col` column in the `plumes` dataset, and, if present, replace the
    corresponding `wind_normalized_em_col` values where the cutoff indicator is True with 
    a randomly sampled value from the remainder of all non-cutoff plume `wind_normalized_em_col`
    values. 

    If no `cutoff_col` column exists in the plumes table, just return the table unchanged 
    (implicitly, this assumes that all plumes were *not* cut off).

    Args:
        plumes (pd.DataFrame):
            Plumes dataset with at least a wind-normalized emissions column.
        
        cutoff_col (str):
            The name of the column containing the boolean indicator for 
            whether or not the identified plume was cut off by the field of 
            view.

        wind_normalized_em_col (str):
            The name of the column in `plumes` containing the wind-normalized emissions.

    Returns:
        pd.DataFrame:
            A new copy of the `plumes` table, but with wind normalized emissions values 
            in rows where the cutoff indicator is True replaced with sampled values from 
            all the rows where the indicator is False.
    """

    # If there is no column representing plume cutoff status, there's no adjustment to be had.
    if cutoff_col not in plumes.columns:
        return plumes

    # Segregate plumes into cutoff/non-cutoff
    non_cutoff = plumes.loc[plumes[cutoff_col]==False]
    cutoff = plumes.loc[plumes[cutoff_col]==True]
    n_cutoff, _  = cutoff.shape
    
    # If there are any cut off plumes, 
    if n_cutoff>0:
        windnorm_em_resample = non_cutoff[wind_normalized_em_col].sample(n_cutoff,replace=True)
        cutoff[wind_normalized_em_col] = windnorm_em_resample

    plumes = pd.concat([cutoff,non_cutoff])

    plumes.drop(columns=cutoff_col,inplace=True)
    
    return plumes