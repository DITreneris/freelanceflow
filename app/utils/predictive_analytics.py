"""
Predictive analytics utilities for sales forecasting and trend analysis.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from sqlmodel import Session, select
from app.models import Deal, Client

class PredictiveAnalytics:
    """Predictive analytics utility class for sales forecasting and trend analysis"""
    
    @staticmethod
    def forecast_pipeline_value(
        db: Session, 
        days_history: int = 90, 
        days_forecast: int = 30
    ) -> Dict[str, Any]:
        """
        Forecast pipeline value for the next n days based on historical data
        
        Args:
            db: Database session
            days_history: Number of days of historical data to use
            days_forecast: Number of days to forecast
            
        Returns:
            Dictionary containing forecast data
        """
        # Calculate start date for historical data
        start_date = datetime.utcnow() - timedelta(days=days_history)
        
        # Get all deals updated within the date range
        statement = select(Deal).where(Deal.updated_at >= start_date)
        deals = db.exec(statement).all()
        
        # Convert to DataFrame for easier analysis
        deals_data = [{
            'id': deal.id,
            'value': deal.value / 100,  # Convert to dollars
            'stage': deal.stage,
            'updated_at': deal.updated_at.date()
        } for deal in deals]
        
        if not deals_data:
            return {
                "forecast_dates": [],
                "lead_forecast": [],
                "proposed_forecast": [],
                "won_forecast": [],
                "total_forecast": [],
                "confidence": 0
            }
        
        # Create DataFrame
        df = pd.DataFrame(deals_data)
        
        # Group by date and calculate daily values
        date_range = pd.date_range(start=start_date.date(), end=datetime.utcnow().date())
        daily_values = PredictiveAnalytics._calculate_daily_values(df, date_range)
        
        # Generate forecast
        forecast_dates = [
            (datetime.utcnow() + timedelta(days=i)).strftime('%Y-%m-%d') 
            for i in range(1, days_forecast + 1)
        ]
        
        # Simple forecasting method: linear regression
        lead_forecast, lead_conf = PredictiveAnalytics._linear_forecast(
            daily_values['dates_num'], daily_values['lead_values'], days_forecast
        )
        
        proposed_forecast, proposed_conf = PredictiveAnalytics._linear_forecast(
            daily_values['dates_num'], daily_values['proposed_values'], days_forecast
        )
        
        won_forecast, won_conf = PredictiveAnalytics._linear_forecast(
            daily_values['dates_num'], daily_values['won_values'], days_forecast
        )
        
        # Calculate total forecast and overall confidence
        total_forecast = [
            lead + proposed + won 
            for lead, proposed, won in zip(lead_forecast, proposed_forecast, won_forecast)
        ]
        
        # Average confidence across all forecasts
        confidence = round((lead_conf + proposed_conf + won_conf) / 3, 2)
        
        return {
            "forecast_dates": forecast_dates,
            "lead_forecast": lead_forecast,
            "proposed_forecast": proposed_forecast,
            "won_forecast": won_forecast,
            "total_forecast": total_forecast,
            "confidence": confidence
        }
    
    @staticmethod
    def analyze_sales_velocity(
        db: Session, 
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Calculate sales velocity metrics
        
        Formula: Sales Velocity = (# of Opportunities × Win Rate × Average Deal Size) ÷ Sales Cycle Length
        
        Args:
            db: Database session
            days: Number of days to analyze
            
        Returns:
            Dictionary containing sales velocity metrics
        """
        # Calculate start date for analysis period
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get all deals updated within the date range
        statement = select(Deal).where(Deal.updated_at >= start_date)
        deals = db.exec(statement).all()
        
        if not deals:
            return {
                "sales_velocity": 0,
                "opportunities": 0,
                "win_rate": 0,
                "avg_deal_size": 0,
                "sales_cycle_length": 0,
                "revenue_projection": 0
            }
        
        # Count opportunities (all deals)
        opportunities = len(deals)
        
        # Calculate win rate (deals in 'won' stage / all deals)
        won_deals = [deal for deal in deals if deal.stage == 'won']
        win_rate = len(won_deals) / opportunities if opportunities > 0 else 0
        
        # Calculate average deal size
        avg_deal_size = sum(deal.value for deal in deals) / opportunities / 100 if opportunities > 0 else 0
        
        # Estimate sales cycle length (use 30 days as default if not enough data)
        sales_cycle_length = 30
        
        # Calculate sales velocity
        sales_velocity = (opportunities * win_rate * avg_deal_size) / sales_cycle_length if sales_cycle_length > 0 else 0
        
        # Project revenue for next 30 days
        revenue_projection = sales_velocity * 30
        
        return {
            "sales_velocity": round(sales_velocity, 2),
            "opportunities": opportunities,
            "win_rate": round(win_rate * 100, 1),
            "avg_deal_size": round(avg_deal_size, 2),
            "sales_cycle_length": sales_cycle_length,
            "revenue_projection": round(revenue_projection, 2)
        }
    
    @staticmethod
    def predict_churn_risk(
        db: Session
    ) -> List[Dict[str, Any]]:
        """
        Identify clients with high churn risk
        
        Args:
            db: Database session
            
        Returns:
            List of clients with risk scores
        """
        # Get all clients with their deals
        statement = select(Client)
        clients = db.exec(statement).all()
        
        client_risks = []
        
        for client in clients:
            # Calculate days since last interaction
            if not client.deals:
                continue
                
            # Sort deals by update date
            sorted_deals = sorted(client.deals, key=lambda d: d.updated_at, reverse=True)
            
            # Calculate days since most recent deal update
            days_since_update = (datetime.utcnow() - sorted_deals[0].updated_at).days
            
            # Count total deals and won deals
            total_deals = len(client.deals)
            won_deals = sum(1 for deal in client.deals if deal.stage == 'won')
            
            # Calculate win rate
            win_rate = won_deals / total_deals if total_deals > 0 else 0
            
            # Calculate risk score (0-100)
            # Factors: days since last update, win rate, total deals
            risk_score = min(100, days_since_update * 0.5 * (1 - win_rate) * (1 / (total_deals ** 0.5)))
            
            client_risks.append({
                "id": client.id,
                "name": client.name,
                "email": client.email,
                "days_since_update": days_since_update,
                "total_deals": total_deals,
                "win_rate": round(win_rate * 100, 1),
                "risk_score": round(risk_score, 1),
                "risk_level": "High" if risk_score > 70 else "Medium" if risk_score > 30 else "Low"
            })
        
        # Sort by risk score (highest first)
        client_risks.sort(key=lambda x: x["risk_score"], reverse=True)
        
        return client_risks
    
    @staticmethod
    def forecast_deal_outcomes(
        db: Session, 
        stage: str = 'proposed'
    ) -> List[Dict[str, Any]]:
        """
        Forecast outcome probabilities for deals in a given stage
        
        Args:
            db: Database session
            stage: Deal stage to analyze (usually 'proposed')
            
        Returns:
            List of deals with outcome probabilities
        """
        # Get deals in the specified stage
        statement = select(Deal).where(Deal.stage == stage)
        deals = db.exec(statement).all()
        
        if not deals:
            return []
        
        # We'll use a simple model based on deal value and client history
        deal_predictions = []
        
        for deal in deals:
            # Get client
            client = db.get(Client, deal.client_id)
            if not client:
                continue
            
            # Get client's deal history
            client_deals = [d for d in client.deals if d.id != deal.id]
            
            # Calculate client's win rate
            won_deals = sum(1 for d in client_deals if d.stage == 'won')
            client_win_rate = won_deals / len(client_deals) if client_deals else 0.5
            
            # Adjust win probability based on deal value and client history
            # This is a simplified model - in real life you'd use more factors and ML
            base_probability = 0.5
            
            # Value factor: larger deals have lower win probability
            avg_deal_value = sum(d.value for d in deals) / len(deals)
            value_factor = 1.0 - min(0.3, (deal.value - avg_deal_value) / avg_deal_value * 0.1)
            
            # Client history factor
            history_factor = 0.5 + client_win_rate * 0.5
            
            # Calculate final probability
            win_probability = base_probability * value_factor * history_factor
            win_probability = max(0.1, min(0.9, win_probability))
            
            # Get client name
            client_name = client.name if client else "Unknown"
            
            deal_predictions.append({
                "id": deal.id,
                "client_id": deal.client_id,
                "client_name": client_name,
                "value": deal.value / 100,  # Convert to dollars
                "win_probability": round(win_probability * 100, 1),
                "expected_value": round((deal.value / 100) * win_probability, 2),
                "recommendation": "Focus" if win_probability > 0.7 else "Review" if win_probability > 0.4 else "Reconsider"
            })
        
        # Sort by expected value (highest first)
        deal_predictions.sort(key=lambda x: x["expected_value"], reverse=True)
        
        return deal_predictions
    
    @staticmethod
    def _calculate_daily_values(
        df: pd.DataFrame, 
        date_range: pd.DateRange
    ) -> Dict[str, Any]:
        """
        Calculate daily values for each stage from deal data
        
        Args:
            df: DataFrame with deal data
            date_range: Date range to calculate values for
            
        Returns:
            Dictionary with daily values for each stage
        """
        dates_array = np.array(range(len(date_range)))
        lead_values = []
        proposed_values = []
        won_values = []
        
        for i, date in enumerate(date_range):
            date_deals = df[df['updated_at'] <= date]
            
            # Sum values by stage
            lead_value = date_deals[date_deals['stage'] == 'lead']['value'].sum()
            proposed_value = date_deals[date_deals['stage'] == 'proposed']['value'].sum()
            won_value = date_deals[date_deals['stage'] == 'won']['value'].sum()
            
            lead_values.append(float(lead_value))
            proposed_values.append(float(proposed_value))
            won_values.append(float(won_value))
        
        return {
            "dates_num": dates_array,
            "lead_values": lead_values,
            "proposed_values": proposed_values,
            "won_values": won_values
        }
    
    @staticmethod
    def _linear_forecast(
        x: np.ndarray, 
        y: List[float], 
        days_forecast: int
    ) -> Tuple[List[float], float]:
        """
        Generate forecast using linear regression
        
        Args:
            x: X values (dates as numbers)
            y: Y values (historical values)
            days_forecast: Number of days to forecast
            
        Returns:
            Tuple of (forecast_values, confidence)
        """
        # Handle empty or single value datasets
        if len(y) <= 1:
            return [y[0] if y else 0] * days_forecast, 0.0
        
        # Fit linear regression model
        try:
            coefficients = np.polyfit(x, y, 1)
            slope = coefficients[0]
            intercept = coefficients[1]
            
            # Calculate R-squared (coefficient of determination)
            y_pred = slope * x + intercept
            ss_total = np.sum((y - np.mean(y)) ** 2)
            ss_residual = np.sum((y - y_pred) ** 2)
            r_squared = 1 - (ss_residual / ss_total) if ss_total > 0 else 0
            
            # Generate forecast values
            forecast_x = np.array(range(max(x) + 1, max(x) + days_forecast + 1))
            forecast_values = slope * forecast_x + intercept
            
            # Ensure no negative values
            forecast_values = [max(0, val) for val in forecast_values]
            
            return forecast_values, r_squared
        except:
            # Fall back to simple average if regression fails
            avg_value = sum(y) / len(y)
            return [avg_value] * days_forecast, 0.0 