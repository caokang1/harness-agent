package com.example.shop.stock.mapper;

import com.example.shop.common.dto.StockDTO;
import java.util.List;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface StockMapper {

    List<StockDTO> selectLow(@Param("threshold") Integer threshold);

    @Update("update stock set qty = qty + #{delta} where id = #{stockId}")
    int adjust(@Param("stockId") Long stockId, @Param("delta") Integer delta);

    @Insert("insert into stock_log (stock_id, delta) values (#{stockId}, #{delta})")
    int log(@Param("stockId") Long stockId, @Param("delta") Integer delta);
}
